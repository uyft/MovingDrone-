#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DroneCrowd 通用定位效果可视化程序

功能：
1. 生成真实点与预测点对比视频；
2. 支持单个序列、多个序列或全部测试序列；
3. 自动读取测试图片、annotations/*.mat 和预测TXT；
4. 使用与定位评测一致的一对一匹配逻辑；
5. 输出每帧 TP、FP、FN、Precision、Recall、F1；
6. 可选保存对比帧图片。

颜色说明（OpenCV BGR）：
- 绿色圆：匹配成功的真实人头
- 黄色十字：匹配成功的预测点
- 蓝色圆：漏检真实人头
- 红色十字：误检预测点
- 青色线：真实点与预测点的匹配连线

示例：
    # 序列11
    python visualize_localization.py --seqs 11

    # 多个序列
    python visualize_localization.py --seqs 11 15 21

    # 全部测试序列
    python visualize_localization.py --all

    # 推理结果还没跑全，只处理已有帧
    python visualize_localization.py --all --allow-partial

    # 同时保存逐帧图片
    python visualize_localization.py --seqs 11 --save-frames
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat


IMAGE_PATTERN = re.compile(
    r"^img(?P<sequence>\d{3})(?P<frame>\d{3})\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)


def read_test_list(path: Path) -> list[int]:
    if not path.exists():
        raise FileNotFoundError(f"找不到测试列表：{path}")

    values = np.loadtxt(str(path), dtype=np.int64)
    values = np.atleast_1d(values).reshape(-1)
    return [int(value) for value in values]


def discover_images(image_dir: Path, sequence_id: int) -> list[tuple[int, Path]]:
    images: list[tuple[int, Path]] = []

    for path in image_dir.glob(f"img{sequence_id:03d}*"):
        match = IMAGE_PATTERN.match(path.name)
        if not match:
            continue

        if int(match.group("sequence")) != sequence_id:
            continue

        images.append((int(match.group("frame")), path))

    return sorted(images, key=lambda item: item[0])


def load_annotation(annotation_path: Path) -> np.ndarray:
    """
    返回：
        frame_id(从1开始), track_id, x1, y1, x2, y2
    """
    if not annotation_path.exists():
        raise FileNotFoundError(f"找不到标注文件：{annotation_path}")

    mat = loadmat(str(annotation_path))
    if "anno" not in mat:
        raise KeyError(
            f"{annotation_path} 中不存在 anno，实际变量：{sorted(mat.keys())}"
        )

    anno = np.asarray(mat["anno"], dtype=np.float64)

    if anno.ndim != 2 or anno.shape[1] < 6:
        raise ValueError(
            f"标注格式异常：{annotation_path}，形状为 {anno.shape}"
        )

    result = anno[:, :6].copy()
    result[:, 0] += 1.0
    return result


def load_predictions(path: Path) -> np.ndarray:
    """
    返回 N×3：
        x, y, confidence
    """
    if path.stat().st_size == 0:
        return np.empty((0, 3), dtype=np.float64)

    data = np.loadtxt(str(path), dtype=np.float64)

    if data.size == 0:
        return np.empty((0, 3), dtype=np.float64)

    if data.ndim == 1:
        data = data.reshape(1, -1)

    if data.shape[1] != 3:
        data = data.T

    if data.ndim != 2 or data.shape[1] != 3:
        raise ValueError(
            f"预测文件格式应为3列 [x,y,confidence]：{path}，"
            f"实际形状 {data.shape}"
        )

    return data


def match_frame(
    gt_boxes: np.ndarray,
    predictions: np.ndarray,
    threshold: float,
) -> tuple[list[tuple[int, int, float]], set[int], set[int]]:
    """
    使用与官方评测一致的置信度优先、一对一匹配方式。

    gt_boxes:
        N×4，格式 [x1,y1,x2,y2]
    predictions:
        M×3，格式 [x,y,confidence]
    """
    if len(gt_boxes) == 0 or len(predictions) == 0:
        return [], set(), set()

    gt_centers = np.column_stack(
        (
            (gt_boxes[:, 0] + gt_boxes[:, 2]) / 2.0,
            (gt_boxes[:, 1] + gt_boxes[:, 3]) / 2.0,
        )
    )

    order = np.argsort(-predictions[:, 2], kind="mergesort")
    ordered_predictions = predictions[order]

    distances = np.linalg.norm(
        ordered_predictions[:, None, :2] - gt_centers[None, :, :],
        axis=2,
    )

    matched_gt: set[int] = set()
    matched_pred_original: set[int] = set()
    matches: list[tuple[int, int, float]] = []

    for ordered_index, original_pred_index in enumerate(order):
        best_gt = -1
        best_distance = float(threshold)

        for gt_index in range(len(gt_centers)):
            if gt_index in matched_gt:
                continue

            distance = float(distances[ordered_index, gt_index])
            if distance <= best_distance:
                best_distance = distance
                best_gt = gt_index

        if best_gt >= 0:
            matched_gt.add(best_gt)
            matched_pred_original.add(int(original_pred_index))
            matches.append(
                (best_gt, int(original_pred_index), best_distance)
            )

    return matches, matched_gt, matched_pred_original


def draw_legend(image: np.ndarray) -> None:
    x0, y0 = 24, 24
    width, height = 520, 168

    overlay = image.copy()
    cv2.rectangle(
        overlay,
        (x0, y0),
        (x0 + width, y0 + height),
        (0, 0, 0),
        -1,
    )
    cv2.addWeighted(overlay, 0.62, image, 0.38, 0, image)

    entries = [
        ("Matched GT", "circle", (0, 255, 0)),
        ("Matched prediction", "cross", (0, 255, 255)),
        ("Missed GT", "circle", (255, 0, 0)),
        ("False prediction", "cross", (0, 0, 255)),
    ]

    for index, (label, shape, color) in enumerate(entries):
        y = y0 + 34 + index * 31
        point = (x0 + 22, y)

        if shape == "circle":
            cv2.circle(image, point, 6, color, 2)
        else:
            cv2.drawMarker(
                image,
                point,
                color,
                markerType=cv2.MARKER_CROSS,
                markerSize=13,
                thickness=2,
            )

        cv2.putText(
            image,
            label,
            (x0 + 44, y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.66,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )


def draw_metrics(
    image: np.ndarray,
    sequence_id: int,
    frame_id: int,
    gt_count: int,
    prediction_count: int,
    tp: int,
    fp: int,
    fn: int,
    precision: float,
    recall: float,
    f1: float,
) -> None:
    lines = [
        f"Sequence {sequence_id:03d}  Frame {frame_id:03d}",
        f"GT: {gt_count}   Pred: {prediction_count}",
        f"TP: {tp}   FP: {fp}   FN: {fn}",
        f"Precision: {precision:.3f}",
        f"Recall: {recall:.3f}",
        f"F1: {f1:.3f}",
    ]

    x0 = max(24, image.shape[1] - 610)
    y0 = 24
    width = min(580, image.shape[1] - x0 - 18)
    height = 224

    overlay = image.copy()
    cv2.rectangle(
        overlay,
        (x0, y0),
        (x0 + width, y0 + height),
        (0, 0, 0),
        -1,
    )
    cv2.addWeighted(overlay, 0.62, image, 0.38, 0, image)

    for index, text in enumerate(lines):
        cv2.putText(
            image,
            text,
            (x0 + 22, y0 + 38 + index * 33),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )


def process_sequence(
    sequence_id: int,
    dataset_root: Path,
    prediction_root: Path,
    output_root: Path,
    distance_threshold: float,
    fps: float,
    allow_partial: bool,
    save_frames: bool,
    max_frames: int | None,
) -> dict:
    image_dir = dataset_root / "test_data" / "images"
    annotation_path = dataset_root / "annotations" / f"{sequence_id:05d}.mat"

    image_items = discover_images(image_dir, sequence_id)
    if not image_items:
        raise FileNotFoundError(
            f"序列 {sequence_id:03d} 没有发现测试图片"
        )

    if max_frames is not None:
        image_items = image_items[:max_frames]

    annotation = load_annotation(annotation_path)

    sequence_output = output_root / f"sequence_{sequence_id:03d}"
    sequence_output.mkdir(parents=True, exist_ok=True)

    frames_output = sequence_output / "frames"
    if save_frames:
        frames_output.mkdir(parents=True, exist_ok=True)

    video_path = sequence_output / (
        f"sequence_{sequence_id:03d}_localization_compare.mp4"
    )
    csv_path = sequence_output / "per_frame_visual_metrics.csv"

    first_image = cv2.imread(str(image_items[0][1]))
    if first_image is None:
        raise RuntimeError(f"图片读取失败：{image_items[0][1]}")

    height, width = first_image.shape[:2]
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    if not writer.isOpened():
        raise RuntimeError(
            f"视频写入器创建失败：{video_path}。"
            "请检查 OpenCV 是否支持 mp4v。"
        )

    rows: list[dict] = []
    missing_count = 0

    try:
        for index, (frame_id, image_path) in enumerate(image_items, start=1):
            prediction_path = (
                prediction_root
                / f"img{sequence_id:03d}{frame_id:03d}_loc.txt"
            )

            if not prediction_path.exists():
                missing_count += 1

                if allow_partial:
                    print(
                        f"[跳过] 序列 {sequence_id:03d} "
                        f"第 {frame_id:03d} 帧缺少预测文件"
                    )
                    continue

                raise FileNotFoundError(
                    f"缺少预测文件：{prediction_path}。"
                    "中途检查可添加 --allow-partial。"
                )

            image = cv2.imread(str(image_path))
            if image is None:
                raise RuntimeError(f"图片读取失败：{image_path}")

            frame_gt_rows = annotation[
                annotation[:, 0].astype(np.int64) == frame_id
            ]
            gt_boxes = frame_gt_rows[:, 2:6]
            predictions = load_predictions(prediction_path)

            matches, matched_gt, matched_pred = match_frame(
                gt_boxes,
                predictions,
                distance_threshold,
            )

            tp = len(matches)
            fp = len(predictions) - tp
            fn = len(gt_boxes) - tp

            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            f1 = (
                2.0 * precision * recall / (precision + recall)
                if precision + recall
                else 0.0
            )

            gt_centers = np.column_stack(
                (
                    (gt_boxes[:, 0] + gt_boxes[:, 2]) / 2.0,
                    (gt_boxes[:, 1] + gt_boxes[:, 3]) / 2.0,
                )
            ) if len(gt_boxes) else np.empty((0, 2))

            # 先画匹配连线。
            for gt_index, pred_index, _distance in matches:
                gx, gy = gt_centers[gt_index]
                px, py = predictions[pred_index, :2]

                cv2.line(
                    image,
                    (int(round(gx)), int(round(gy))),
                    (int(round(px)), int(round(py))),
                    (255, 255, 0),
                    1,
                    cv2.LINE_AA,
                )

            # 真实点。
            for gt_index, (x, y) in enumerate(gt_centers):
                point = (int(round(x)), int(round(y)))

                if gt_index in matched_gt:
                    cv2.circle(image, point, 5, (0, 255, 0), 2)
                else:
                    cv2.circle(image, point, 6, (255, 0, 0), 2)

            # 预测点。
            for pred_index, row in enumerate(predictions):
                point = (
                    int(round(row[0])),
                    int(round(row[1])),
                )

                color = (
                    (0, 255, 255)
                    if pred_index in matched_pred
                    else (0, 0, 255)
                )

                cv2.drawMarker(
                    image,
                    point,
                    color,
                    markerType=cv2.MARKER_CROSS,
                    markerSize=12,
                    thickness=2,
                )

            draw_legend(image)
            draw_metrics(
                image=image,
                sequence_id=sequence_id,
                frame_id=frame_id,
                gt_count=len(gt_boxes),
                prediction_count=len(predictions),
                tp=tp,
                fp=fp,
                fn=fn,
                precision=precision,
                recall=recall,
                f1=f1,
            )

            writer.write(image)

            if save_frames:
                frame_path = (
                    frames_output
                    / f"img{sequence_id:03d}{frame_id:03d}_compare.jpg"
                )
                cv2.imwrite(str(frame_path), image)

            rows.append(
                {
                    "sequence_id": sequence_id,
                    "frame_id": frame_id,
                    "image_name": image_path.name,
                    "gt_count": len(gt_boxes),
                    "prediction_count": len(predictions),
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                }
            )

            if index == 1 or index % 25 == 0 or index == len(image_items):
                print(
                    f"序列 {sequence_id:03d}："
                    f"{index}/{len(image_items)} 帧"
                )
    finally:
        writer.release()

    if not rows:
        raise ValueError(
            f"序列 {sequence_id:03d} 没有生成任何可视化帧"
        )

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        fieldnames = list(rows[0].keys())
        csv_writer = csv.DictWriter(file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)

    total_tp = sum(row["tp"] for row in rows)
    total_fp = sum(row["fp"] for row in rows)
    total_fn = sum(row["fn"] for row in rows)

    total_precision = (
        total_tp / (total_tp + total_fp)
        if total_tp + total_fp
        else 0.0
    )
    total_recall = (
        total_tp / (total_tp + total_fn)
        if total_tp + total_fn
        else 0.0
    )
    total_f1 = (
        2.0 * total_precision * total_recall
        / (total_precision + total_recall)
        if total_precision + total_recall
        else 0.0
    )

    return {
        "sequence_id": sequence_id,
        "visualized_frames": len(rows),
        "missing_prediction_files": missing_count,
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "precision": total_precision,
        "recall": total_recall,
        "f1": total_f1,
        "video_path": str(video_path),
        "csv_path": str(csv_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DroneCrowd 通用定位对比视频生成程序"
    )

    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--all",
        action="store_true",
        help="处理 testlist.txt 中的全部序列",
    )
    selection.add_argument(
        "--seqs",
        nargs="+",
        type=int,
        help="处理指定序列，例如 --seqs 11 15 21",
    )

    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("../dataset"),
    )
    parser.add_argument(
        "--pred-dir",
        type=Path,
        default=Path("cyc_pts"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation_output/localization_visualization"),
    )
    parser.add_argument(
        "--test-list",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="匹配距离阈值，默认10像素",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=15.0,
        help="输出视频帧率，默认15",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="跳过缺少预测文件的帧",
    )
    parser.add_argument(
        "--save-frames",
        action="store_true",
        help="除视频外，同时保存每帧对比图片",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="每个序列最多处理多少帧，默认全部",
    )

    return parser.parse_args()


def resolve_path(script_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (script_root / path).resolve()


def main() -> None:
    args = parse_args()
    script_root = Path(__file__).resolve().parent

    dataset_root = resolve_path(script_root, args.dataset_root)
    prediction_root = resolve_path(script_root, args.pred_dir)
    output_root = resolve_path(script_root, args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    test_list = (
        args.test_list
        if args.test_list is not None
        else dataset_root / "testlist.txt"
    )
    test_list = resolve_path(script_root, test_list)

    official_sequences = read_test_list(test_list)

    if args.seqs:
        sequence_ids = args.seqs
    else:
        sequence_ids = official_sequences

    print("=" * 72)
    print("DroneCrowd 定位效果可视化")
    print("数据集：", dataset_root)
    print("预测目录：", prediction_root)
    print("输出目录：", output_root)
    print("序列：", sequence_ids)
    print("匹配阈值：", args.threshold, "像素")
    print("=" * 72)

    summary_rows: list[dict] = []

    for index, sequence_id in enumerate(sequence_ids, start=1):
        print(
            f"\n[{index}/{len(sequence_ids)}] "
            f"处理序列 {sequence_id:03d}"
        )

        summary = process_sequence(
            sequence_id=sequence_id,
            dataset_root=dataset_root,
            prediction_root=prediction_root,
            output_root=output_root,
            distance_threshold=args.threshold,
            fps=args.fps,
            allow_partial=args.allow_partial,
            save_frames=args.save_frames,
            max_frames=args.max_frames,
        )
        summary_rows.append(summary)

        print("视频：", summary["video_path"])
        print(
            "Precision/Recall/F1："
            f"{summary['precision']:.4f}/"
            f"{summary['recall']:.4f}/"
            f"{summary['f1']:.4f}"
        )

    summary_path = output_root / "visualization_summary.csv"
    with summary_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        fieldnames = list(summary_rows[0].keys())
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\n" + "=" * 72)
    print("全部可视化生成完成")
    print("汇总文件：", summary_path)
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError, RuntimeError) as error:
        print(f"\n生成失败：{error}", file=sys.stderr)
        sys.exit(1)
