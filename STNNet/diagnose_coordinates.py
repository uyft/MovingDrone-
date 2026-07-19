from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.spatial import cKDTree


SEQ_ID = 11
FRAME_ID = 1

root = Path(__file__).resolve().parent
dataset_root = root.parent / "dataset"

point_gt_path = (
    dataset_root
    / "test_data"
    / "ground_truth"
    / f"GT_img{SEQ_ID:03d}{FRAME_ID:03d}.mat"
)

annotation_path = (
    dataset_root
    / "annotations"
    / f"{SEQ_ID:05d}.mat"
)

prediction_path = (
    root
    / "cyc_pts"
    / f"img{SEQ_ID:03d}{FRAME_ID:03d}_loc.txt"
)


def load_point_gt(path: Path) -> np.ndarray:
    mat = loadmat(str(path))
    points = mat["image_info"][0, 0][0, 0][0]
    return np.asarray(points[:, :2], dtype=np.float64)


def load_predictions(path: Path) -> np.ndarray:
    data = np.loadtxt(str(path), dtype=np.float64)

    if data.ndim == 1:
        data = data.reshape(1, -1)

    return data[:, :2]


def nearest_report(
    name: str,
    points: np.ndarray,
    reference: np.ndarray,
) -> None:
    print("\n" + "=" * 65)
    print(name)
    print("=" * 65)
    print("点数量：", len(points))

    if len(points) == 0:
        return

    print(
        "x范围：",
        round(float(points[:, 0].min()), 2),
        "到",
        round(float(points[:, 0].max()), 2),
    )
    print(
        "y范围：",
        round(float(points[:, 1].min()), 2),
        "到",
        round(float(points[:, 1].max()), 2),
    )

    tree = cKDTree(reference)
    distances, _ = tree.query(points, k=1)

    print("最近距离最小值：", round(float(distances.min()), 4))
    print("最近距离中位数：", round(float(np.median(distances)), 4))
    print("最近距离平均值：", round(float(distances.mean()), 4))
    print("最近距离最大值：", round(float(distances.max()), 4))
    print("距离 <= 5 像素：", int(np.sum(distances <= 5)))
    print("距离 <= 10 像素：", int(np.sum(distances <= 10)))
    print("距离 <= 20 像素：", int(np.sum(distances <= 20)))


for required_path in (
    point_gt_path,
    annotation_path,
    prediction_path,
):
    if not required_path.exists():
        raise FileNotFoundError(f"文件不存在：{required_path}")


# 直接的人头点标注
point_gt = load_point_gt(point_gt_path)

# 视频级标注
annotation_mat = loadmat(str(annotation_path))

print("annotation MAT变量：", annotation_mat.keys())

if "anno" not in annotation_mat:
    raise KeyError("annotations文件中没有anno变量")

anno = np.asarray(annotation_mat["anno"], dtype=np.float64)

print("anno完整形状：", anno.shape)
print("anno前5行：")
print(anno[:5])

# 官方程序使用 anno第一列 + 1 作为帧号
frame_rows = anno[
    (anno[:, 0].astype(np.int64) + 1) == FRAME_ID
]

print("\n当前帧anno行数：", len(frame_rows))
print("当前帧anno前5行：")
print(frame_rows[:5])

if frame_rows.shape[1] < 6:
    raise ValueError(
        f"anno列数不足，实际形状为：{frame_rows.shape}"
    )

# 三种可能的解释方式
annotation_raw_xy = frame_rows[:, 2:4]

annotation_xywh_center = np.column_stack(
    (
        frame_rows[:, 2] + frame_rows[:, 4] / 2.0,
        frame_rows[:, 3] + frame_rows[:, 5] / 2.0,
    )
)

annotation_xyxy_center = np.column_stack(
    (
        (frame_rows[:, 2] + frame_rows[:, 4]) / 2.0,
        (frame_rows[:, 3] + frame_rows[:, 5]) / 2.0,
    )
)

predictions = load_predictions(prediction_path)


print("\n" + "#" * 65)
print("基本信息")
print("#" * 65)
print("点标注文件：", point_gt_path)
print("视频标注文件：", annotation_path)
print("预测文件：", prediction_path)
print("直接人头GT数量：", len(point_gt))
print("anno当前帧数量：", len(frame_rows))
print("预测点数量：", len(predictions))

nearest_report(
    "方案A：anno第三、四列直接作为人头点 x、y",
    annotation_raw_xy,
    point_gt,
)

nearest_report(
    "方案B：anno格式按 x、y、width、height 计算中心",
    annotation_xywh_center,
    point_gt,
)

nearest_report(
    "方案C：anno格式按 x1、y1、x2、y2 计算中心",
    annotation_xyxy_center,
    point_gt,
)

nearest_report(
    "模型预测点 与 直接人头GT的距离",
    predictions,
    point_gt,
)

print("\n" + "#" * 65)
print("判断方法")
print("#" * 65)
print("哪一种anno解释的距离中位数最接近0，哪一种就是正确格式。")
print("模型预测点如果有大量点距离GT小于10像素，说明模型坐标正常。")
