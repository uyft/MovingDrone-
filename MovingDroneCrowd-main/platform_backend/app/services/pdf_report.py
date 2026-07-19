"""
PDF 报告生成模块
使用 fpdf2 + matplotlib 生成中文 PDF 任务报告，含解读文字与总结
"""
import os
import math
import tempfile
from datetime import datetime

import numpy as np

from app.config import RESULT_DIR

# ── 中文字体 ──────────────────────────────────────────────────
_FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_FONT_PATH_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

# ── 页面常量 ──────────────────────────────────────────────────
PAGE_W, PAGE_H = 210, 297  # A4
MARGIN = 18
BODY_W = PAGE_W - 2 * MARGIN

# ── 品牌色 ────────────────────────────────────────────────────
C_PRIMARY = (20, 60, 120)
C_ACCENT  = (0, 150, 200)
C_DARK    = (30, 30, 30)
C_MEDIUM  = (100, 100, 100)
C_LIGHT   = (200, 200, 200)
C_BG      = (240, 245, 250)
C_WHITE   = (255, 255, 255)


# ================================================================
#  主入口
# ================================================================
def build_task_report(task_id: str) -> str | None:
    from app.db import db_get_task, db_get_result

    task = db_get_task(task_id)
    result = db_get_result(task_id)
    if not task or not result:
        return None

    frames = result.get("frames", [])
    counts = [f.get("count", 0) for f in frames]
    peak_counts = [len(f.get("peaks", [])) for f in frames]

    n_frames = len(counts) or 1
    total_people = sum(counts)
    avg_count = total_people / n_frames
    max_count = max(counts) if counts else 0
    min_count = min(counts) if counts else 0
    peak_frame_idx = counts.index(max_count) + 1 if counts else 0
    std_count = float(np.std(counts)) if counts else 0.0
    cv = (std_count / avg_count * 100) if avg_count > 0 else 0.0   # 变异系数

    # 密度等级
    density_label = _density_level(avg_count)
    # 趋势判断
    trend = _trend_analysis(counts)
    # 高密度帧占比
    high_threshold = avg_count + std_count
    high_density_ratio = sum(1 for c in counts if c > high_threshold) / n_frames * 100
    # 四分位数
    q25 = float(np.percentile(counts, 25)) if counts else 0.0
    q75 = float(np.percentile(counts, 75)) if counts else 0.0

    tmpdir = tempfile.mkdtemp(prefix="pdf_report_")
    try:
        chart_path = _make_count_chart(counts, task["filename"], tmpdir)
        frame_imgs = _extract_key_frames(
            result.get("video_path", ""), frames, counts, peak_frame_idx, tmpdir)

        pdf_path = os.path.join(RESULT_DIR, f"{task_id}_report.pdf")
        _build_pdf(
            pdf_path=pdf_path,
            task=task, result=result, n_frames=n_frames,
            total_people=total_people, avg_count=avg_count,
            max_count=max_count, min_count=min_count,
            peak_frame_idx=peak_frame_idx, std_count=std_count,
            cv=cv, density_label=density_label, trend=trend,
            high_density_ratio=high_density_ratio,
            q25=q25, q75=q75,
            counts=counts, peak_counts=peak_counts,
            chart_path=chart_path, frame_imgs=frame_imgs,
            tmpdir=tmpdir,
        )
        return pdf_path
    except Exception:
        import traceback
        traceback.print_exc()
        return None
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ================================================================
#  辅助分析函数
# ================================================================
def _density_level(avg: float) -> str:
    if avg < 15:
        return "低密度（稀疏）"
    elif avg < 50:
        return "中低密度"
    elif avg < 100:
        return "中等密度"
    elif avg < 300:
        return "中高密度"
    else:
        return "高密度（密集）"


def _trend_analysis(counts: list[int]) -> dict:
    """判断整体趋势：上升/下降/平稳"""
    n = len(counts)
    if n < 10:
        return {"direction": "平稳", "desc": "视频帧数较少，无明显变化趋势。"}
    half = n // 2
    first_half_avg = np.mean(counts[:half])
    second_half_avg = np.mean(counts[half:])
    change_pct = (second_half_avg - first_half_avg) / max(first_half_avg, 1) * 100

    xs = np.arange(n)
    slope = np.polyfit(xs, counts, 1)[0]

    if change_pct > 15:
        direction = "明显上升"
        desc = (f"后半段平均人数（{second_half_avg:.1f}）较前半段（{first_half_avg:.1f}）"
                f"增长 {change_pct:.0f}%，场景内人群数量呈上升趋势。")
    elif change_pct > 5:
        direction = "小幅上升"
        desc = (f"后半段平均人数（{second_half_avg:.1f}）较前半段（{first_half_avg:.1f}）"
                f"增长 {change_pct:.0f}%，人群数量略有增加。")
    elif change_pct > -5:
        direction = "基本平稳"
        desc = "视频前后段人群数量变化不大，整体保持稳定。"
    elif change_pct > -15:
        direction = "小幅下降"
        desc = (f"后半段平均人数（{second_half_avg:.1f}）较前半段（{first_half_avg:.1f}）"
                f"减少 {abs(change_pct):.0f}%，人群数量略有减少。")
    else:
        direction = "明显下降"
        desc = (f"后半段平均人数（{second_half_avg:.1f}）较前半段（{first_half_avg:.1f}）"
                f"减少 {abs(change_pct):.0f}%，场景内人群数量呈下降趋势。")
    return {"direction": direction, "desc": desc, "change_pct": change_pct}


def _model_label(name: str) -> str:
    m = {
        "STEERER": "STEERER 密度估计模型",
        "YOLO11": "YOLO11 目标检测模型",
        "GD3A_VGG16": "GD³A + VGG16 检测模型",
        "GD3A_ResNet50": "GD³A + ResNet50 检测模型",
        "STNNet": "STNNet 时空网络模型",
    }
    return m.get(name, name)


# ================================================================
#  人数曲线图
# ================================================================
def _make_count_chart(counts: list[int], title: str, tmpdir: str) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    font_manager.fontManager.addfont(_FONT_PATH)
    prop = font_manager.FontProperties(fname=_FONT_PATH)
    matplotlib.rcParams["font.family"] = prop.get_name()
    matplotlib.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=150)
    xs = list(range(1, len(counts) + 1))
    avg = np.mean(counts) if counts else 0

    ax.plot(xs, counts, linewidth=1.0, color="#1478C8", alpha=0.9)
    ax.fill_between(xs, counts, alpha=0.12, color="#1478C8")
    ax.axhline(y=avg, color="#E05050", linewidth=0.8, linestyle="--", alpha=0.7)
    ax.text(len(counts) * 0.98, avg + max(counts) * 0.02, f"均值 {avg:.1f}",
            fontsize=7, color="#E05050", ha="right", va="bottom")

    if counts:
        max_i = int(np.argmax(counts))
        ax.annotate(f"峰值 {counts[max_i]}",
                    xy=(max_i + 1, counts[max_i]),
                    xytext=(max_i + 1 + len(counts) * 0.06, counts[max_i] * 1.08),
                    fontsize=7, color="#C85020",
                    arrowprops=dict(arrowstyle="->", color="#C85020", lw=0.8))

    ax.set_xlabel("帧序号", fontsize=9)
    ax.set_ylabel("人数", fontsize=9)
    ax.set_title(f"人群计数曲线 — {title}", fontsize=11, fontweight="bold")
    ax.set_xlim(1, len(counts) or 1)
    ax.tick_params(labelsize=7)
    ax.grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout(pad=1.2)

    chart_path = os.path.join(tmpdir, "count_chart.png")
    fig.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return chart_path


# ================================================================
#  关键帧截图
# ================================================================
def _extract_key_frames(video_path: str, frames: list, counts: list,
                        peak_idx: int, tmpdir: str) -> list[dict]:
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return []

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or len(frames)
    indices = {peak_idx}
    for frac in [1, total // 3, total * 2 // 3, total]:
        indices.add(max(1, min(total, frac)))

    results = []
    for fi in sorted(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi - 1)
        ret, frame_bgr = cap.read()
        if not ret:
            continue
        cnt = counts[fi - 1] if fi - 1 < len(counts) else 0
        h, w = frame_bgr.shape[:2]
        label = f"Frame #{fi}  |  Count: {cnt}"
        font_scale = max(0.6, w / 900)
        thickness = max(1, int(font_scale * 1.5))
        cv2.putText(frame_bgr, label, (12, max(28, int(h * 0.04))),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 220, 255), thickness, cv2.LINE_AA)
        img_path = os.path.join(tmpdir, f"frame_{fi:06d}.jpg")
        cv2.imwrite(img_path, frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
        results.append({"label": f"第 {fi} 帧", "path": img_path,
                        "frame_idx": fi, "count": cnt})
    cap.release()
    return results


# ================================================================
#  PDF 构建主流程
# ================================================================
def _build_pdf(pdf_path, task, result, n_frames, total_people, avg_count,
               max_count, min_count, peak_frame_idx, std_count, cv,
               density_label, trend, high_density_ratio, q25, q75,
               counts, peak_counts, chart_path, frame_imgs, tmpdir):
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("CJK", "", _FONT_PATH)
    pdf.add_font("CJK", "B", _FONT_PATH_BOLD)

    # ── 封面 ──
    pdf.add_page()
    _draw_cover(pdf, task, result)

    # ── 任务概览 ──
    pdf.add_page()
    _draw_section_title(pdf, "一、任务概览")
    _draw_overview_table(pdf, task, result, n_frames)
    _draw_paragraph(pdf,
        f"本报告基于 {_model_label(task.get('model', ''))} 对视频「{task.get('filename', '')}」"
        f"进行逐帧人群计数分析。视频共 {n_frames} 帧，分辨率 "
        f"{result.get('width', 0)}×{result.get('height', 0)}，帧率 {result.get('fps', 0):.0f} FPS，"
        f"总处理耗时 {result.get('total_time', 0):.1f} 秒。"
        f"以下各章节将从统计指标、时间变化趋势和空间分布三个维度对该视频的人群特征进行详细解读。")

    # ── 统计摘要 ──
    _draw_section_title(pdf, "二、统计摘要")
    _draw_stats(pdf, total_people, avg_count, max_count, min_count,
                peak_frame_idx, std_count, q25, q75)

    # 统计解读
    _draw_paragraph(pdf,
        f"该视频的人群密度等级为「{density_label}」，每帧平均约 {avg_count:.1f} 人，"
        f"变异系数（CV）为 {cv:.1f}%，说明人群数量波动"
        f"{'较大' if cv > 40 else '适中' if cv > 20 else '较小'}。"
        f"单帧最高人数出现在第 {peak_frame_idx} 帧，达到 {max_count} 人；"
        f"最低为 {min_count} 人。标准差 {std_count:.1f}，"
        f"约 {high_density_ratio:.0f}% 的帧人数超过「均值+1σ」阈值，"
        f"这些高密度时段是需要重点关注的人群聚集期。")

    _draw_paragraph(pdf,
        f"从四分位分布来看，25% 的帧人数低于 {q25:.0f}，75% 的帧人数低于 {q75:.0f}，"
        f"中间 50% 帧的人数集中在 [{q25:.0f}, {q75:.0f}] 区间内。"
        f"这说明该场景中人群规模的整体波动范围约为 {q75 - q25:.0f} 人。")

    # ── 人数曲线 ──
    if os.path.exists(chart_path):
        pdf.add_page()
        _draw_section_title(pdf, "三、人群计数曲线")
        img_w = BODY_W
        img_h = img_w * 0.4
        pdf.image(chart_path, x=MARGIN, y=pdf.get_y() + 2, w=img_w, h=img_h)

        # 曲线解读
        pdf.set_y(pdf.get_y() + img_h + 4)
        _draw_paragraph(pdf,
            f"上图为逐帧人数变化曲线，蓝色实线为每帧检测到的人数，红色虚线为整体均值 "
            f"（{avg_count:.1f} 人/帧），橙色箭头标记了峰值位置。"
            f"从曲线形态可以看出：{trend['desc']}")

        if max_count > avg_count * 2:
            _draw_paragraph(pdf,
                f"需特别关注的是，峰值帧人数（{max_count} 人）超过均值的 2 倍，"
                f"表明该时间点出现了瞬时人群聚集现象。建议结合关键帧截图"
                f"（第五章）查看该时刻的场景状态，判断是否存在异常事件或安全隐患。")

    # ── 密度分布直方图（新增） ──
    if len(counts) > 1:
        bar_path = _make_density_histogram(counts, tmpdir)
        if bar_path and os.path.exists(bar_path):
            pdf.set_y(pdf.get_y() + 4)
            _draw_paragraph(pdf,
                "下方为人数分布直方图，横轴为人数区间，纵轴为该区间内的帧数。"
                "它直观展示了人群规模在不同区间的出现频率。")
            bar_h = BODY_W * 0.35
            pdf.image(bar_path, x=MARGIN, y=pdf.get_y() + 2, w=BODY_W, h=bar_h)

    # ── 关键帧 ──
    if frame_imgs:
        pdf.add_page()
        _draw_section_title(pdf, "四、关键帧截图")
        _draw_frames_grid(pdf, frame_imgs)
        # 等网格画完，获取底部 y（在 _draw_frames_grid 内部已处理位置）

        # 关键帧解读：需要知道 _draw_frames_grid 结束后光标位置
        # 在 _draw_frames_grid 后追加说明
        n_imgs = len(frame_imgs)
        rows = math.ceil(n_imgs / 2)
        cell_h = (BODY_W / 2 - 4) * 0.5625
        pdf.set_y(pdf.get_y() + rows * (cell_h + 10) + 4)

        peak_img = next((f for f in frame_imgs if f["frame_idx"] == peak_frame_idx), None)
        _draw_paragraph(pdf,
            f"上图为从视频中抽取的 {n_imgs} 个关键帧（包含首帧、末帧、1/3 处、2/3 处以及峰值帧）。"
            f"{'第 ' + str(peak_frame_idx) + ' 帧为峰值帧，人数达到 ' + str(max_count) + ' 人，该时刻人群最为密集。' if peak_img else ''}"
            f"通过这些关键帧，可以直观对比不同时间点的人群分布情况。")

    # ── 帧统计附表 ──
    pdf.add_page()
    _draw_section_title(pdf, "五、帧统计附表")
    _draw_frame_table(pdf, counts, peak_counts)
    _draw_paragraph(pdf,
        "上表为采样后的帧级统计数据（为避免表格过长，按比例间隔采样）。"
        "「人数」列为该帧检测到的总人数，「检测点」列为密度图中提取的局部峰值点数量。"
        "完整逐帧数据可通过平台的 JSON 导出功能获取。")

    # ── 总结 ──
    pdf.add_page()
    _draw_conclusion(pdf, task, avg_count, max_count, min_count, peak_frame_idx,
                     std_count, cv, density_label, trend, high_density_ratio,
                     n_frames, total_people, q25, q75)

    pdf.output(pdf_path)


# ================================================================
#  新增：密度分布直方图
# ================================================================
def _make_density_histogram(counts, tmpdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_manager.fontManager.addfont(_FONT_PATH)
    prop = font_manager.FontProperties(fname=_FONT_PATH)
    matplotlib.rcParams["font.family"] = prop.get_name()
    matplotlib.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(7, 2.5), dpi=130)
    bins = max(8, min(30, int(np.sqrt(len(counts))) * 2))
    ax.hist(counts, bins=bins, color="#1478C8", alpha=0.75, edgecolor="white", linewidth=0.5)
    ax.axvline(np.mean(counts), color="#E05050", linestyle="--", linewidth=1.0, label=f"均值 {np.mean(counts):.1f}")
    ax.set_xlabel("每帧人数", fontsize=9)
    ax.set_ylabel("帧数", fontsize=9)
    ax.set_title("人群数量分布直方图", fontsize=11, fontweight="bold")
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    ax.grid(True, linestyle=":", alpha=0.35)
    fig.tight_layout(pad=1.2)

    bar_path = os.path.join(tmpdir, "density_hist.png")
    fig.savefig(bar_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return bar_path


# ================================================================
#  总结与分析
# ================================================================
def _draw_conclusion(pdf, task, avg_count, max_count, min_count,
                     peak_frame_idx, std_count, cv, density_label,
                     trend, high_density_ratio, n_frames, total_people,
                     q25, q75):
    _draw_section_title(pdf, "六、总结与分析")

    # 总体描述
    _draw_paragraph(pdf,
        f"本次分析基于 {_model_label(task.get('model', ''))} 对视频「{task.get('filename', '')}」"
        f"进行了全面的人群计数与时空分布分析。视频共计 {n_frames} 帧，"
        f"累计检测到 {total_people:,} 人次，属于{density_label}场景。以下是关键发现：",
        size=10)

    # 核心发现
    pdf.ln(2)
    pdf.set_font("CJK", "B", 11)
    pdf.set_text_color(*C_PRIMARY)
    pdf.cell(0, 8, "核心发现", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    findings = [
        (f"人群密度等级", f"{density_label}，平均每帧 {avg_count:.1f} 人"),
        (f"变化趋势", f"{trend['direction']}（{trend['change_pct']:+.0f}%），{trend['desc']}"),
        (f"波动程度", f"标准差 {std_count:.1f}，变异系数 {cv:.1f}%——人群数量"
                      f"{'波动剧烈，存在明显的人员聚集和消散过程' if cv > 40 else '有一定波动，呈现自然的流动状态' if cv > 20 else '相对稳定，人群规模变化不大'}"),
        (f"峰值特征", f"第 {peak_frame_idx} 帧达到峰值 {max_count} 人，"
                      f"该时刻为全视频人群最密集的时间点。建议重点关注该帧前后的场景变化。"),
        (f"高密度时段", f"约 {high_density_ratio:.0f}% 的帧人数超过均值+1σ（{avg_count + std_count:.0f} 人），"
                        f"这些时段的人群密度需要特别关注。"),
        (f"人群分布", f"中间 50% 帧的人数在 [{q25:.0f}, {q75:.0f}] 之间，"
                      f"最低 {min_count} 人，最高 {max_count} 人。"),
    ]

    for i, (title, detail) in enumerate(findings):
        bullet_y = pdf.get_y()
        pdf.set_fill_color(*C_BG)
        pdf.set_draw_color(*C_LIGHT)
        pdf.set_line_width(0.2)
        card_w = BODY_W
        # 先估算高度：每行约 6mm
        card_h = 13
        pdf.rect(MARGIN, bullet_y, card_w, card_h, "DF")

        pdf.set_xy(MARGIN + 3, bullet_y + 1.5)
        pdf.set_font("CJK", "B", 9)
        pdf.set_text_color(*C_PRIMARY)
        pdf.cell(28, 5, title)

        pdf.set_font("CJK", "", 9)
        pdf.set_text_color(*C_DARK)
        pdf.set_x(MARGIN + 32)
        pdf.multi_cell(card_w - 36, 5, detail)
        pdf.ln(3)

    # 总体评价
    pdf.ln(4)
    _draw_section_title(pdf, "总体评价")
    _draw_paragraph(pdf, _build_overall_assessment(
        density_label, trend, cv, high_density_ratio, max_count, avg_count), size=10)

    # 建议
    pdf.ln(4)
    _draw_section_title(pdf, "建议与展望")
    recommendations = _build_recommendations(density_label, cv, trend, max_count, avg_count)
    for i, rec in enumerate(recommendations, 1):
        pdf.set_font("CJK", "B", 9)
        pdf.set_text_color(*C_DARK)
        pdf.set_x(MARGIN + 2)
        pdf.cell(8, 6, f"{i}.")
        pdf.set_font("CJK", "", 9)
        pdf.multi_cell(BODY_W - 10, 6, rec)
        pdf.ln(1)

    # 报告结尾
    pdf.ln(8)
    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(0.3)
    y = pdf.get_y()
    pdf.line(MARGIN + 30, y, PAGE_W - MARGIN - 30, y)
    pdf.ln(5)
    pdf.set_font("CJK", "", 9)
    pdf.set_text_color(*C_MEDIUM)
    pdf.cell(0, 6, "— 报告结束 —", align="C")
    pdf.ln(5)
    pdf.set_font("CJK", "", 8)
    pdf.cell(0, 5, f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}     "
                    "DroneCrowd 无人机人群智能感知平台", align="C")


def _build_overall_assessment(density_label, trend, cv, high_density_ratio, max_count, avg_count):
    """生成总体评价段落"""
    parts = [f"综合来看，该视频呈现{density_label}的人群特征。"]

    # 趋势评价
    if trend["direction"] in ("明显上升", "明显下降"):
        parts.append(f"人群数量在视频时间范围内{trend['direction']}，变化幅度较大，"
                    f"可能与场景中发生的事件（如集会、散场等）相关。")
    elif trend["direction"] in ("小幅上升", "小幅下降"):
        parts.append(f"人群数量{trend['direction']}，整体变化较为温和。")
    else:
        parts.append("人群数量整体保持平稳，未见明显的增减趋势。")

    # 波动评价
    if cv > 50:
        parts.append(f"人群波动剧烈（CV={cv:.0f}%），说明场景中存在明显的人员聚集与消散交替过程，"
                    f"可能对应特定事件周期。")
    elif cv > 25:
        parts.append(f"人群有一定波动（CV={cv:.0f}%），属于正常的人员流动范围。")
    else:
        parts.append(f"人群波动较小（CV={cv:.0f}%），密度分布相对均匀。")

    # 峰值评价
    if max_count > avg_count * 3:
        parts.append(f"峰值人数远超均值，存在瞬时极端聚集情况，建议重点排查该时刻的安全风险。")
    elif max_count > avg_count * 2:
        parts.append(f"峰值人数明显高于均值，存在阶段性的人群聚集高峰。")

    return "".join(parts)


def _build_recommendations(density_label, cv, trend, max_count, avg_count):
    """生成建议列表"""
    recs = []

    if "高密度" in density_label or "中高" in density_label:
        recs.append(
            "该场景人群密度较高，建议在峰值时段加强现场管控，设置分流通道和引导标识，"
            "避免因过度拥挤导致的安全隐患。")
    else:
        recs.append(
            "当前场景人群密度处于可控范围。建议保持常规监控，定期进行人数统计以建立"
            "正常基线，便于及时发现异常波动。")

    if cv > 40:
        recs.append(
            f"人群数量波动较大（CV={cv:.0f}%），建议关注波动背后的原因——是自然流动还是事件驱动。"
            f"可结合时间戳与现场日志，定位波动发生的具体时段，分析触发因素。")

    if trend["direction"] in ("明显上升", "明显下降"):
        recs.append(
            f"人群呈{trend['direction']}趋势，如该趋势持续，建议提前部署相应的人力与物资调配预案。")

    if max_count > avg_count * 2.5:
        recs.append(
            f"峰值人数（{max_count} 人）远超均值（{avg_count:.0f} 人），建议针对峰值时段设置预警阈值，"
            f"实现自动化告警，确保在人群快速聚集时能及时响应。")

    recs.append(
        "建议定期（如每周/每月）对同一场景进行重复分析，积累历史数据后可通过纵向对比"
        "发现人群模式的周期性变化，为资源调度提供数据支撑。")

    recs.append(
        "如需更详细的个体轨迹与运动模式分析，可使用平台的 Tracking 模式或 STNNet "
        "时空网络模型，获取每个人的运动轨迹，进一步分析人群流动方向与热点区域。")

    return recs


# ================================================================
#  Paragraph 工具：自动换行
# ================================================================
def _draw_paragraph(pdf, text: str, size: int = 9):
    """以指定字号输出一段文字，自动在 BODY_W 宽度内换行。"""
    pdf.set_font("CJK", "", size)
    pdf.set_text_color(*C_DARK)
    pdf.set_x(MARGIN)
    pdf.multi_cell(BODY_W, size * 0.6 + 1.2, text, align="L")
    pdf.ln(2)


# ================================================================
#  封面
# ================================================================
def _draw_cover(pdf, task, result):
    pdf.set_fill_color(*C_BG)
    pdf.rect(0, 0, PAGE_W, PAGE_H, "F")
    pdf.set_fill_color(*C_PRIMARY)
    pdf.rect(0, 0, PAGE_W, 6, "F")

    pdf.set_y(50)
    pdf.set_font("CJK", "B", 28)
    pdf.set_text_color(*C_PRIMARY)
    pdf.cell(0, 14, "DroneCrowd", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CJK", "", 12)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(0, 8, "无人机人群智能感知平台", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(14)

    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(0.4)
    y = pdf.get_y()
    pdf.line(MARGIN + 30, y, PAGE_W - MARGIN - 30, y)
    pdf.ln(6)

    pdf.set_font("CJK", "B", 22)
    pdf.set_text_color(*C_DARK)
    pdf.cell(0, 12, "人群分析任务报告", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    card_x = MARGIN + 15
    card_w = BODY_W - 30
    pdf.set_fill_color(*C_WHITE)
    pdf.set_draw_color(*C_LIGHT)
    pdf.set_line_width(0.3)
    card_y = pdf.get_y()
    card_h = 48
    pdf.rect(card_x, card_y, card_w, card_h, "DF")
    pdf.set_xy(card_x + 4, card_y + 5)
    pdf.set_font("CJK", "", 10)
    pdf.set_text_color(*C_MEDIUM)

    info_lines = [
        f"任务 ID：{task['task_id']}",
        f"视频文件：{task.get('filename', '—')}",
        f"分析模型：{task.get('model', '—')}   |   分析模式：{task.get('mode', '—')}",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    for line in info_lines:
        pdf.set_x(card_x + 4)
        pdf.cell(card_w - 8, 8, line, new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(PAGE_H - 25)
    pdf.set_font("CJK", "", 9)
    pdf.set_text_color(*C_MEDIUM)
    pdf.cell(0, 6, "— 本报告由 DroneCrowd 平台自动生成 —", align="C")


# ================================================================
#  章节标题
# ================================================================
def _draw_section_title(pdf, title: str):
    pdf.set_fill_color(*C_PRIMARY)
    pdf.rect(MARGIN, pdf.get_y() + 1, 3, 8, "F")
    pdf.set_x(MARGIN + 6)
    pdf.set_font("CJK", "B", 14)
    pdf.set_text_color(*C_DARK)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


# ================================================================
#  任务概览表格
# ================================================================
def _draw_overview_table(pdf, task, result, n_frames):
    pdf.set_font("CJK", "", 10)
    pdf.set_text_color(*C_DARK)
    col_w = BODY_W / 2

    rows = [
        ("视频文件", task.get("filename", "—")),
        ("分析模型", _model_label(task.get("model", ""))),
        ("分析模式", task.get("mode", "—")),
        ("视频分辨率", f"{result.get('width', 0)} × {result.get('height', 0)}"),
        ("帧率 (FPS)", f"{result.get('fps', 0):.1f}"),
        ("总帧数", str(n_frames)),
        ("文件大小", f"{task.get('size_mb', 0):.1f} MB"),
        ("处理耗时", f"{result.get('total_time', 0):.1f} 秒"),
    ]

    for i, (label, val) in enumerate(rows):
        x = MARGIN + (i % 2) * col_w
        if i % 2 == 0 and i > 0:
            pdf.ln()
        pdf.set_xy(x, pdf.get_y())
        pdf.set_font("CJK", "B", 10)
        pdf.set_text_color(*C_MEDIUM)
        pdf.cell(col_w * 0.38, 8, label + "：", align="R")
        pdf.set_font("CJK", "", 10)
        pdf.set_text_color(*C_DARK)
        pdf.cell(col_w * 0.58, 8, str(val))
    pdf.ln(12)


# ================================================================
#  统计摘要卡片
# ================================================================
def _draw_stats(pdf, total, avg, mx, mn, peak_idx, std, q25, q75):
    cards = [
        ("累计总人数", f"{total:,}"),
        ("平均每帧人数", f"{avg:.1f}"),
        ("最大单帧人数", f"{mx}"),
        ("最小单帧人数", f"{mn}"),
        ("峰值帧号", f"#{peak_idx}"),
        ("标准差", f"{std:.1f}"),
        ("下四分位数 (Q1)", f"{q25:.0f}"),
        ("上四分位数 (Q3)", f"{q75:.0f}"),
    ]

    card_w = (BODY_W - 16) / 3
    card_h = 18
    pdf.ln(2)

    for i, (label, val) in enumerate(cards):
        col = i % 3
        row = i // 3
        x = MARGIN + col * (card_w + 8)
        y0 = pdf.get_y() + row * (card_h + 5)
        pdf.set_fill_color(*C_BG)
        pdf.set_draw_color(*C_LIGHT)
        pdf.set_line_width(0.2)
        pdf.rect(x, y0, card_w, card_h, "DF")
        pdf.set_xy(x + 2, y0 + 1.5)
        pdf.set_font("CJK", "", 8)
        pdf.set_text_color(*C_MEDIUM)
        pdf.cell(card_w - 4, 5, label, align="C")
        pdf.set_xy(x + 2, y0 + 7)
        pdf.set_font("CJK", "B", 13)
        pdf.set_text_color(*C_PRIMARY)
        pdf.cell(card_w - 4, 8, val, align="C")

    pdf.ln(((len(cards) - 1) // 3 + 1) * (card_h + 5) + 6)


# ================================================================
#  关键帧网格
# ================================================================
def _draw_frames_grid(pdf, frame_imgs):
    n = len(frame_imgs)
    if n == 0:
        return
    cols = 2
    rows = math.ceil(n / cols)
    cell_w = BODY_W / cols - 4
    cell_h = cell_w * 0.5625

    for i, fi in enumerate(frame_imgs):
        col = i % cols
        row = i // cols
        x = MARGIN + col * (cell_w + 8)
        y = pdf.get_y() + row * (cell_h + 10)
        if os.path.exists(fi["path"]):
            pdf.image(fi["path"], x=x, y=y, w=cell_w, h=cell_h)
        pdf.set_xy(x, y + cell_h + 1)
        pdf.set_font("CJK", "", 8)
        pdf.set_text_color(*C_DARK)
        pdf.cell(cell_w, 5, f"{fi['label']}  |  人数: {fi['count']}", align="C")


# ================================================================
#  帧统计附表
# ================================================================
def _draw_frame_table(pdf, counts, peak_counts):
    n = len(counts)
    step = max(1, math.ceil(n / 40))
    col_w = [12, 28, 28, 28]
    start_x = MARGIN + 8

    pdf.set_fill_color(*C_PRIMARY)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("CJK", "B", 9)
    headers = ["序号", "帧号", "人数", "检测点"]
    pdf.set_x(start_x)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 8, h, border=0, fill=True, align="C")
    pdf.ln()

    for row_i, fi in enumerate(range(0, n, step)):
        pdf.set_x(start_x)
        pdf.set_font("CJK", "", 8)
        pdf.set_fill_color(*(C_BG if row_i % 2 == 0 else C_WHITE))
        pdf.set_text_color(*C_DARK)
        vals = [str(row_i + 1), str(fi + 1), str(counts[fi]), str(peak_counts[fi])]
        for j, v in enumerate(vals):
            pdf.cell(col_w[j], 7, v, border=0, fill=True, align="C")
        pdf.ln()
