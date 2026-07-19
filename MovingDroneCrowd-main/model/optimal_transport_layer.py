import torch
from copy import deepcopy
import torch.nn as nn
import torch.nn.functional as F
from model.dustbin_score_predictor import DustbinScorePredictor
def MLP(channels: list[int], do_bn: bool = True) -> nn.Module:
    """ Multi-layer perceptron """
    n = len(channels)
    layers = []
    for i in range(1, n):
        layers.append(
            nn.Conv1d(channels[i - 1], channels[i], kernel_size=1, bias=True))
        if i < (n-1):
            if do_bn:
                layers.append(nn.BatchNorm1d(channels[i]))
            layers.append(nn.ReLU())
    return nn.Sequential(*layers)


def normalize_keypoints(kpts, image_shape):
    """ Normalize keypoints locations based on image image_shape"""
    _, _, height, width = image_shape
    one = kpts.new_tensor(1)
    size = torch.stack([one*width, one*height])[None]
    center = size / 2
    scaling = size.max(1, keepdim=True).values * 0.7
    return (kpts - center[:, None, :]) / scaling[:, None, :]


class KeypointEncoder(nn.Module):
    """ Joint encoding of visual appearance and location using MLPs"""
    def __init__(self, feature_dim: int, layers: list[int]) -> None:
        super().__init__()
        self.encoder = MLP([2] + layers + [feature_dim])
        nn.init.constant_(self.encoder[-1].bias, 0.0)

    def forward(self, kpts):
        inputs = kpts.transpose(1, 2)
        return self.encoder(inputs)

def attention(query: torch.Tensor, key: torch.Tensor, value: torch.Tensor) -> tuple[torch.Tensor,torch.Tensor]:
    dim = query.shape[1]
    scores = torch.einsum('bdhn,bdhm->bhnm', query, key) / dim**.5
    prob = torch.nn.functional.softmax(scores, dim=-1)
    return torch.einsum('bhnm,bdhm->bdhn', prob, value), prob


class MultiHeadedAttention(nn.Module):
    """ Multi-head attention to increase model expressivitiy """
    def __init__(self, num_heads: int, d_model: int):
        super().__init__()
        assert d_model % num_heads == 0
        self.dim = d_model // num_heads
        self.num_heads = num_heads
        self.merge = nn.Conv1d(d_model, d_model, kernel_size=1)
        self.proj = nn.ModuleList([deepcopy(self.merge) for _ in range(3)])

    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor) -> torch.Tensor:
        batch_dim = query.size(0)
        query, key, value = [l(x).view(batch_dim, self.dim, self.num_heads, -1)
                             for l, x in zip(self.proj, (query, key, value))]
        x, _ = attention(query, key, value)
        return self.merge(x.contiguous().view(batch_dim, self.dim*self.num_heads, -1))


class AttentionalPropagation(nn.Module):
    def __init__(self, feature_dim: int, num_heads: int):
        super().__init__()
        self.attn = MultiHeadedAttention(num_heads, feature_dim)
        self.mlp = MLP([feature_dim*2, feature_dim*2, feature_dim])
        nn.init.constant_(self.mlp[-1].bias, 0.0)

    def forward(self, x: torch.Tensor, source: torch.Tensor) -> torch.Tensor:
        message = self.attn(x, source, source)
        return self.mlp(torch.cat([x, message], dim=1))


class AttentionalGNN(nn.Module):
    def __init__(self, feature_dim: int, layer_names: list[str]) -> None:
        super().__init__()
        self.layers = nn.ModuleList([
            AttentionalPropagation(feature_dim, 4)
            for _ in range(len(layer_names))])
        self.names = layer_names

    def forward(self, desc0: torch.Tensor, desc1: torch.Tensor, fast_inference: bool = False) -> tuple[torch.Tensor,torch.Tensor]:
        # ⚡ 快速推理模式：只用前 6 层（3 self + 3 cross），而不是 18 层
        num_layers = min(6, len(self.layers)) if fast_inference else len(self.layers)
        for idx in range(num_layers):
            layer = self.layers[idx]
            name = self.names[idx]
            if name == 'cross':
                src0, src1 = desc1, desc0
            else:  # if name == 'self':
                src0, src1 = desc0, desc1
            delta0, delta1 = layer(desc0, src0), layer(desc1, src1)
            desc0, desc1 = (desc0 + delta0), (desc1 + delta1)
        return desc0, desc1
    
class Optimal_Transport_Layer(nn.Module):
    def __init__(self, config):
        super(Optimal_Transport_Layer, self).__init__()
        self.iters = config['sinkhorn_iterations']
        self.feature_dim = config['feature_dim']
        self.matched_threshold = config['matched_threshold']

        self.kenc = KeypointEncoder(
            self.feature_dim, [32, 64, 128, 256])

        self.gnn = AttentionalGNN(
            feature_dim=self.feature_dim, layer_names=['self', 'cross'] * 9)

        self.final_proj = nn.Conv1d(
            self.feature_dim, self.feature_dim,
            kernel_size=1, bias=True)
        self.dustbin_score_predictor = DustbinScorePredictor(hidden_dim=self.feature_dim, nhead=8, num_layers=4)
    
    def _fast_bin_score(self, scores, mask0=None, mask1=None):
        """
        ⚡ 快速版 dustbin score：直接从匹配分数分布统计得到
        避免运行 heavy Transformer（原版 DustbinScorePredictor 的 O(L²) 自注意力）
        
        思路：匹配分数矩阵中的最大值分布反映了匹配质量。
        好的匹配对分数高且尖锐（只有一个明显峰值），差的匹配分数平缓。
        用分数矩阵的稀疏性/峰值度来估计 dustbin 权重。
        """
        B, N, M = scores.shape
        device = scores.device
        
        # 计算每个点与最佳匹配的分数差距（gap 越大说明匹配越确定）
        top2_vals = torch.topk(scores, k=2, dim=2, largest=True)[0]  # (B, N, 2)
        gap = top2_vals[:, :, 0] - top2_vals[:, :, 1]  # (B, N) gap 大 = 匹配确定
        
        # 只考虑有效点的 gap
        if mask0 is not None:
            gap = gap.masked_fill(mask0, 0.0)
        
        # 用平均 gap 的对数来估计 bin_score（gap 小 → bin 大，表示很多不确定匹配）
        # 缩放因子：原模型 bin_score 通常在 [-5, 5] 范围
        valid_N = mask0.size(1) - mask0.sum(dim=1, keepdim=True).clamp(min=1) if mask0 is not None else N
        mean_gap = gap.sum(dim=1, keepdim=True) / valid_N.clamp(min=1)  # (B, 1)
        
        # 将 gap 映射到 bin_score 空间
        # gap ∈ [0, ~20], 目标 bin_score ∈ [-3, 3]
        bin_score = (mean_gap.squeeze(-1) - 5.0) * 0.5  # (B,)
        return bin_score.clamp(-5.0, 5.0)
        
    @property
    def loss(self):
        return self.matching_loss
    
    def forward(self, data, top_k=5, match_gt=None, ignore=False, fast_inference=False):
        desc0, desc1 = data['descriptors0'], data['descriptors1']
        kpts0, kpts1 = data['keypoints0'], data['keypoints1']
        mask0 = data.get('mask0', None)  # (B, N) bool: True = padding
        mask1 = data.get('mask1', None)
            
        # Keypoint normalization.
        kpts0 = normalize_keypoints(kpts0, data['shape'])
        kpts1 = normalize_keypoints(kpts1, data['shape'])
        
        desc0 = desc0 + self.kenc(kpts0)
        desc1 = desc1 + self.kenc(kpts1)

        # Multi-layer Transformer network.
        desc0, desc1 = self.gnn(desc0, desc1, fast_inference=fast_inference)
        
        # Final MLP projection.
        mdesc0, mdesc1 = self.final_proj(desc0), self.final_proj(desc1)

        # Compute matching descriptor distance.
        sim_matrix = torch.einsum('bdn,bdm->bnm', mdesc0, mdesc1)
        scores = sim_matrix / self.feature_dim ** .5

        # ⚡ 传入 mask 到 dustbin predictor，屏蔽 padding 区域
        if fast_inference:
            # 快速模式：用分数分布估计 bin_score，跳过 heavy Transformer
            bin_score = self._fast_bin_score(scores, mask0, mask1)
        else:
            bin_score = self.dustbin_score_predictor(mdesc0, mdesc1, mask1=mask0, mask2=mask1)  # (B, 1)
        
        # ⚡ 推理时用更少的 Sinkhorn 迭代
        sinkhorn_iters = self.iters // 5 if fast_inference else self.iters
        
        # Run the optimal transport.
        scores = log_optimal_transport(
            scores, bin_score,
            iters=sinkhorn_iters)

        tmp_scores = scores[:, :-1, :-1]  # (B, N, M)
        B, N, M = tmp_scores.shape

        K = min(top_k, M, N)  # top-K threshold, can be adjusted
        
        topk_vals0, topk_inds0 = tmp_scores.topk(K, dim=2)  # (B, N, K)
        topk_vals1, topk_inds1 = tmp_scores.transpose(1, 2).topk(K, dim=2)  # (B, M, K)
        
        max0 = tmp_scores.max(2)  # (B, N)
        max1 = tmp_scores.max(1)  # (B, M)
        indices0, indices1 = max0.indices, max1.indices  # (B, N), (B, M)
        
        batch_arange = torch.arange(B, device=scores.device).view(B, 1)    # (B, 1)
        
        row_arange = torch.arange(N, device=scores.device).view(1, N)      # (1, N)
        selected_topk_cols = topk_inds1[batch_arange, indices0]  # (B, N, K)
        mutual0 = (selected_topk_cols == row_arange.unsqueeze(-1)).any(dim=-1)  # (B, N)

        col_arange = torch.arange(M, device=scores.device).view(1, M)
        selected_topk_rows = topk_inds0[batch_arange, indices1]  # (B, M, K)
        mutual1 = (selected_topk_rows == col_arange.unsqueeze(-1)).any(dim=-1)  # (B, M)
        # Apply match threshold
        zero = scores.new_tensor(0)
        mscores0 = torch.where(mutual0, max0.values.exp(), zero)
        mscores1 = torch.where(mutual1, max1.values.exp(), zero)

        valid0 = mutual0 & (mscores0 > self.matched_threshold)
        valid1 = mutual1 & (mscores1 > self.matched_threshold)

        indices0 = torch.where(valid0, indices0, indices0.new_tensor(-1))
        indices1 = torch.where(valid1, indices1, indices1.new_tensor(-1))

        if B == 1:
            scores = scores.squeeze(0).exp()
        else:
            scores = scores.exp()

        if match_gt is not None:
            if B == 1:
                matched_mask = torch.zeros(scores.size()).long().to(scores.device)
                matched_mask[match_gt['a2b'][:, 0], match_gt['a2b'][:, 1]] = 1
                if not ignore: matched_mask[match_gt['un_a'], -1] = 1
                if not ignore: matched_mask[-1, match_gt['un_b']] = 1
                self.matching_loss = -torch.log(scores[matched_mask == 1] + 1e-6)
            else:
                # 批量模式下的 loss 暂不实现（training 时逐对处理）
                self.matching_loss = torch.tensor(0., device=scores.device)

        if B == 1:
            return scores, indices0.squeeze(0), indices1.squeeze(0), mscores0.squeeze(0), mscores1.squeeze(0)
        else:
            return scores, indices0, indices1, mscores0, mscores1

def compute_cost_matrix(P1, P2, F1, F2):
    P1 = P1.float()
    P2 = P2.float()
    P1_expand = P1.unsqueeze(1)  # (N, 1, 2)
    P2_expand = P2.unsqueeze(0)  # (1, M, 2)
    geo_dist = torch.norm(P1_expand - P2_expand, dim=2)  # (N, M)
    geo_dist = geo_dist / geo_dist.max().clamp(min=1e-6)

    F1_t = F1.T.contiguous()  # (N, D)
    F2_t = F2.T.contiguous()  # (M, D)
    F1_norm = F.normalize(F1_t, dim=1)  # (N, D)
    F2_norm = F.normalize(F2_t, dim=1)  # (M, D)
    feat_sim = torch.matmul(F1_norm, F2_norm.T)  # (N, M)
    feat_dist = 1.0 - feat_sim  #

    C = geo_dist + feat_dist  # (N, M)

    return C

def log_sinkhorn_iterations(Z, log_mu, log_nu, iters: int):
    """ Perform Sinkhorn Normalization in Log-space for stability"""

    log_u, log_v = torch.zeros_like(log_mu), torch.zeros_like(log_nu) # initialized with the u,v=1, the log(u)=0, log(v)=0
    for _ in range(iters):
        log_u = log_mu - torch.logsumexp(Z + log_v.unsqueeze(1), dim=2)
        log_v = log_nu - torch.logsumexp(Z + log_u.unsqueeze(2), dim=1)

    return Z + log_u.unsqueeze(2) + log_v.unsqueeze(1)


def log_optimal_transport(scores, alpha, iters: int):
    """ Perform Differentiable Optimal Transport in Log-space for stability"""
    b, m, n = scores.shape
    one = scores.new_tensor(1)
    ms, ns = (m*one).to(scores), (n*one).to(scores)

    bins0 = alpha.expand(b, m, 1)
    bins1 = alpha.expand(b, 1, n)
    alpha = alpha.expand(b, 1, 1)

    couplings = torch.cat([torch.cat([scores, bins0], -1),
                           torch.cat([bins1, alpha], -1)], 1)

    norm = - (ms + ns).log() # normalization in the Log-space (log(1/(m+n)))
    log_mu = torch.cat([norm.expand(m), ns.log()[None] + norm])
    log_nu = torch.cat([norm.expand(n), ms.log()[None] + norm])
    log_mu, log_nu = log_mu[None].expand(b, -1), log_nu[None].expand(b, -1)

    Z = log_sinkhorn_iterations(couplings, log_mu, log_nu, iters)
    score = Z - norm  # multiply probabilities by M+N
    return score


def arange_like(x, dim: int):
    return x.new_ones(x.shape[dim]).cumsum(0) - 1  # traceable in 1.1