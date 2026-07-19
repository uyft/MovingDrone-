#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DroneCrowd 通用定位评测程序（Python 版）

支持：
- 单序列：python evaluate_localization.py --seqs 11
- 多序列：python evaluate_localization.py --seqs 11 15 21
- 全测试集：python evaluate_localization.py --all
- 不完整结果预览：python evaluate_localization.py --all --allow-partial

默认目录：
- 数据集：../dataset
- 预测结果：cyc_pts
- 输出：evaluation_output/localization
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat


IMAGE_RE = re.compile(
    r"^img(?P<seq>\d{3})(?P<frame>\d{3})\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)


@dataclass
class SequenceData:
    seq_id: int
    frame_ids: list[int]
    gt: np.ndarray
    det: np.ndarray
    missing: list[Path]


def load_test_list(path: Path) -> list[int]:
    if not path.exists():
        raise FileNotFoundError(f"找不到测试列表：{path}")
    values = np.atleast_1d(np.loadtxt(path, dtype=np.int64)).reshape(-1)
    return [int(v) for v in values]


def discover_frames(image_dir: Path, seq_id: int) -> list[int]:
    frames = []
    for path in image_dir.glob(f"img{seq_id:03d}*"):
        match = IMAGE_RE.match(path.name)
        if match and int(match.group("seq")) == seq_id:
            frames.append(int(match.group("frame")))
    return sorted(set(frames))


def load_annotation(path: Path) -> np.ndarray:
    """
    官方 anno 前6列：
    frame_index(从0开始), track_id, x, y, width, height

    返回：
    frame_id(从1开始), track_id, x, y, width, height, ignore
    """
    if not path.exists():
        raise FileNotFoundError(f"找不到标注：{path}")

    mat = loadmat(path)
    if "anno" not in mat:
        raise KeyError(f"{path} 中不存在变量 anno")

    anno = np.asarray(mat["anno"], dtype=np.float64)
    if anno.ndim != 2 or anno.shape[1] < 6:
        raise ValueError(f"标注格式异常：{path}，形状={anno.shape}")

    return np.column_stack(
        (
            anno[:, 0] + 1.0,
            anno[:, 1],
            anno[:, 2:6],
            np.zeros(len(anno), dtype=np.float64),
        )
    )


def load_prediction(path: Path, frame_id: int) -> np.ndarray:
    """
    原预测：
    x, y, confidence

    转为官方检测格式：
    frame_id, -1, x-10, y-10, 20, 20, confidence
    """
    if path.stat().st_size == 0:
        return np.empty((0, 7), dtype=np.float64)

    data = np.loadtxt(path, dtype=np.float64)
    if data.size == 0:
        return np.empty((0, 7), dtype=np.float64)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] != 3:
        data = data.T
    if data.ndim != 2 or data.shape[1] != 3:
        raise ValueError(f"预测文件不是3列：{path}，形状={data.shape}")

    n = len(data)
    return np.column_stack(
        (
            np.full(n, frame_id),
            np.full(n, -1),
            data[:, 0] - 10.0,
            data[:, 1] - 10.0,
            np.full(n, 20.0),
            np.full(n, 20.0),
            data[:, 2],
        )
    )


def prepare_sequence(
    seq_id: int,
    dataset_root: Path,
    pred_root: Path,
    allow_partial: bool,
) -> SequenceData:
    image_dir = dataset_root / "test_data" / "images"
    gt_all = load_annotation(
        dataset_root / "annotations" / f"{seq_id:05d}.mat"
    )

    frame_ids = discover_frames(image_dir, seq_id)
    if not frame_ids:
        frame_ids = sorted(set(gt_all[:, 0].astype(int).tolist()))
    if not frame_ids:
        raise ValueError(f"序列 {seq_id:03d} 没有发现任何帧")

    det_parts = []
    missing = []
    evaluated_frames = []

    for frame_id in frame_ids:
        path = pred_root / f"img{seq_id:03d}{frame_id:03d}_loc.txt"
        if not path.exists():
            missing.append(path)
            continue

        evaluated_frames.append(frame_id)
        det = load_prediction(path, frame_id)
        if len(det):
            det_parts.append(det)

    if missing and not allow_partial:
        examples = "\n".join(str(p) for p in missing[:10])
        raise FileNotFoundError(
            f"序列 {seq_id:03d} 缺少 {len(missing)} 个预测文件。\n"
            f"前10个：\n{examples}\n"
            f"中途检查可增加 --allow-partial。"
        )

    if allow_partial:
        if not evaluated_frames:
            raise ValueError(f"序列 {seq_id:03d} 没有可评价帧")
        frame_ids = evaluated_frames

    gt = gt_all[np.isin(gt_all[:, 0].astype(int), frame_ids)]
    det = np.vstack(det_parts) if det_parts else np.empty((0, 7))

    return SequenceData(seq_id, frame_ids, gt, det, missing)


def eval_frame(
    gt0: np.ndarray,
    dt0: np.ndarray,
    threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    复现官方 evalRes.m 的中心距离匹配。

    gt0: [x1, y1, x2, y2, ignore]
    dt0: [x, y, width, height, score]
    """
    gt0 = np.asarray(gt0, dtype=np.float64).reshape(-1, 5)
    dt0 = np.maximum(
        0.0,
        np.asarray(dt0, dtype=np.float64).reshape(-1, 5),
    )

    if len(dt0):
        dt0 = dt0[np.argsort(-dt0[:, 4], kind="mergesort")]
    if len(gt0):
        gt0 = gt0[np.argsort(gt0[:, 4], kind="mergesort")]

    gt = gt0.copy()
    dt = np.column_stack((dt0, np.zeros(len(dt0))))

    if len(gt):
        gt[:, 4] = -gt[:, 4]

    if not len(gt) or not len(dt):
        return gt, dt

    det_centers = np.column_stack(
        (dt[:, 0] + dt[:, 2] / 2, dt[:, 1] + dt[:, 3] / 2)
    )
    # GT格式为：[x1, y1, x2, y2, ignore]
    gt_centers = np.column_stack(
        (
            (gt[:, 0] + gt[:, 2]) / 2.0,
            (gt[:, 1] + gt[:, 3]) / 2.0,
        )
    )
    distances = np.linalg.norm(
        det_centers[:, None, :] - gt_centers[None, :, :],
        axis=2,
    )

    for d in range(len(dt)):
        best_dist = float(threshold)
        best_g = -1
        best_match = 0

        for g in range(len(gt)):
            current = int(gt[g, 4])

            if current == 1:
                continue
            if best_match != 0 and current == -1:
                break

            distance = float(distances[d, g])
            if distance > best_dist:
                continue

            best_dist = distance
            best_g = g
            best_match = 1 if current == 0 else -1

        if best_g < 0:
            continue
        if best_match == -1:
            dt[d, 5] = -1
        elif best_match == 1:
            gt[best_g, 4] = 1
            dt[d, 5] = 1

    return gt, dt


def voc_ap(recall: np.ndarray, precision: np.ndarray) -> float:
    mrec = np.concatenate(([0.0], recall, [1.0]))
    mpre = np.concatenate(([0.0], precision, [0.0]))

    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])

    changed = np.where(mrec[1:] != mrec[:-1])[0] + 1
    return float(
        np.sum((mrec[changed] - mrec[changed - 1]) * mpre[changed])
    )


def evaluate_at_threshold(
    sequences: Iterable[SequenceData],
    threshold: int,
    collect_frames: bool = False,
) -> dict:
    gt_match_parts = []
    det_match_parts = []
    frame_rows = []

    for sequence in sequences:
        for frame_id in sequence.frame_ids:
            gt0 = sequence.gt[
                sequence.gt[:, 0].astype(int) == frame_id,
                2:7,
            ]
            dt0 = sequence.det[
                sequence.det[:, 0].astype(int) == frame_id,
                2:7,
            ]

            gt, dt = eval_frame(gt0, dt0, threshold)
            gt_match_parts.append(gt[:, 4])
            if len(dt):
                det_match_parts.append(dt[:, 4:6])

            if collect_frames:
                tp = int(np.sum(dt[:, 5] == 1))
                fp = int(np.sum(dt[:, 5] == 0))
                fn = int(np.sum(gt[:, 4] == 0))
                precision = tp / (tp + fp) if tp + fp else 0.0
                recall = tp / (tp + fn) if tp + fn else 0.0
                f1 = (
                    2 * precision * recall / (precision + recall)
                    if precision + recall else 0.0
                )
                frame_rows.append(
                    {
                        "sequence_id": sequence.seq_id,
                        "frame_id": frame_id,
                        "gt_count": len(gt0),
                        "prediction_count": len(dt0),
                        "tp": tp,
                        "fp": fp,
                        "fn": fn,
                        "precision": precision,
                        "recall": recall,
                        "f1": f1,
                    }
                )

    gt_matches = (
        np.concatenate(gt_match_parts)
        if gt_match_parts else np.empty(0)
    )
    det_matches = (
        np.vstack(det_match_parts)
        if det_match_parts else np.empty((0, 2))
    )

    if len(det_matches):
        order = np.argsort(-det_matches[:, 0], kind="mergesort")
        matches = det_matches[order, 1]
        tp_curve = np.cumsum(matches == 1)
        fp_curve = np.cumsum(matches == 0)
        recall_curve = tp_curve / max(1, len(gt_matches))
        precision_curve = tp_curve / np.maximum(1, tp_curve + fp_curve)
        ap = voc_ap(recall_curve, precision_curve) * 100.0
    else:
        ap = 0.0

    tp = int(np.sum(det_matches[:, 1] == 1))
    fp = int(np.sum(det_matches[:, 1] == 0))
    fn = int(np.sum(gt_matches == 0))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    return {
        "threshold": threshold,
        "ap_percent": ap,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "per_frame": frame_rows,
    }


def evaluate_range(
    sequences: list[SequenceData],
    threshold_min: int,
    threshold_max: int,
    report_threshold: int,
    verbose: bool = True,
) -> tuple[list[dict], dict]:
    results = []
    report = None

    for threshold in range(threshold_min, threshold_max + 1):
        result = evaluate_at_threshold(
            sequences,
            threshold,
            collect_frames=(threshold == report_threshold),
        )
        results.append(result)
        if threshold == report_threshold:
            report = result

        if verbose:
            print(
                f"距离阈值 {threshold:2d} 像素："
                f"AP={result['ap_percent']:.4f}%"
            )

    if report is None:
        raise ValueError("report-threshold 不在阈值范围内")

    return results, report


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_curve(path: Path, results: list[dict], title: str) -> None:
    x = [r["threshold"] for r in results]
    y = [r["ap_percent"] for r in results]

    plt.figure(figsize=(10, 6))
    plt.plot(x, y, marker="o")
    plt.xlabel("Distance threshold (pixels)")
    plt.ylabel("Average Precision (%)")
    plt.title(title)
    plt.xticks(x)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DroneCrowd 通用定位评测（Python版官方逻辑）"
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        action="store_true",
        help="评价 testlist.txt 中全部序列",
    )
    group.add_argument(
        "--seqs",
        nargs="+",
        type=int,
        help="评价指定序列，如 --seqs 11 15 21",
    )

    parser.add_argument("--dataset-root", type=Path, default=Path("../dataset"))
    parser.add_argument("--pred-dir", type=Path, default=Path("cyc_pts"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation_output/localization"),
    )
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--threshold-min", type=int, default=1)
    parser.add_argument("--threshold-max", type=int, default=25)
    parser.add_argument("--report-threshold", type=int, default=10)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parent

    dataset_root = (
        args.dataset_root
        if args.dataset_root.is_absolute()
        else (root / args.dataset_root).resolve()
    )
    pred_root = (
        args.pred_dir
        if args.pred_dir.is_absolute()
        else (root / args.pred_dir).resolve()
    )
    output_root = (
        args.output_dir
        if args.output_dir.is_absolute()
        else (root / args.output_dir).resolve()
    )

    test_list = load_test_list(dataset_root / "testlist.txt")

    if args.seqs:
        sequence_ids = args.seqs
        run_name = "seq_" + "_".join(f"{v:03d}" for v in sequence_ids)
    else:
        sequence_ids = test_list
        run_name = "all"

    run_dir = output_root / f"run_{run_name}"
    sequence_dir_root = run_dir / "sequences"
    sequence_dir_root.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("数据集：", dataset_root)
    print("预测目录：", pred_root)
    print("评价序列：", sequence_ids)
    print("允许不完整：", args.allow_partial)
    print("=" * 70)

    sequences = []
    missing_rows = []

    for index, seq_id in enumerate(sequence_ids, 1):
        print(f"\n[{index}/{len(sequence_ids)}] 准备序列 {seq_id:03d}")
        sequence = prepare_sequence(
            seq_id,
            dataset_root,
            pred_root,
            args.allow_partial,
        )
        sequences.append(sequence)

        for missing in sequence.missing:
            missing_rows.append(
                {
                    "sequence_id": seq_id,
                    "missing_prediction_file": str(missing),
                }
            )

        print(
            f"帧={len(sequence.frame_ids)}，"
            f"GT={len(sequence.gt)}，"
            f"预测点={len(sequence.det)}，"
            f"缺失={len(sequence.missing)}"
        )

    print("\n计算全局指标...")
    global_results, global_report = evaluate_range(
        sequences,
        args.threshold_min,
        args.threshold_max,
        args.report_threshold,
    )

    sequence_rows = []
    print("\n计算逐序列指标...")

    for index, sequence in enumerate(sequences, 1):
        print(f"[{index}/{len(sequences)}] 序列 {sequence.seq_id:03d}")
        seq_results, seq_report = evaluate_range(
            [sequence],
            args.threshold_min,
            args.threshold_max,
            args.report_threshold,
            verbose=False,
        )
        seq_ap_values = [r["ap_percent"] for r in seq_results]

        row = {
            "sequence_id": sequence.seq_id,
            "evaluated_frame_count": len(sequence.frame_ids),
            "ground_truth_count": len(sequence.gt),
            "prediction_count": len(sequence.det),
            "missing_prediction_count": len(sequence.missing),
            "ap_1_25_percent": float(np.mean(seq_ap_values)),
            f"ap_{args.report_threshold}px_percent": seq_report["ap_percent"],
            f"precision_{args.report_threshold}px": seq_report["precision"],
            f"recall_{args.report_threshold}px": seq_report["recall"],
            f"f1_{args.report_threshold}px": seq_report["f1"],
        }
        sequence_rows.append(row)

        seq_dir = sequence_dir_root / f"sequence_{sequence.seq_id:03d}"
        seq_dir.mkdir(parents=True, exist_ok=True)

        with (seq_dir / "metrics.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    **row,
                    "ap_by_threshold": {
                        str(r["threshold"]): r["ap_percent"]
                        for r in seq_results
                    },
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        save_curve(
            seq_dir / "ap_curve.png",
            seq_results,
            f"DroneCrowd Localization AP - Sequence {sequence.seq_id:03d}",
        )

    global_ap_values = [r["ap_percent"] for r in global_results]
    macro_ap = float(np.mean([r["ap_1_25_percent"] for r in sequence_rows]))

    summary = {
        "evaluated_sequences": sequence_ids,
        "sequence_count": len(sequences),
        "evaluated_frame_count": sum(len(s.frame_ids) for s in sequences),
        "ground_truth_count": sum(len(s.gt) for s in sequences),
        "prediction_count": sum(len(s.det) for s in sequences),
        "missing_prediction_count": len(missing_rows),
        "allow_partial": args.allow_partial,
        "global_ap_1_25_percent": float(np.mean(global_ap_values)),
        "macro_sequence_ap_1_25_percent": macro_ap,
        f"global_ap_{args.report_threshold}px_percent": global_report["ap_percent"],
        f"global_precision_{args.report_threshold}px": global_report["precision"],
        f"global_recall_{args.report_threshold}px": global_report["recall"],
        f"global_f1_{args.report_threshold}px": global_report["f1"],
        f"global_tp_{args.report_threshold}px": global_report["tp"],
        f"global_fp_{args.report_threshold}px": global_report["fp"],
        f"global_fn_{args.report_threshold}px": global_report["fn"],
        "ap_by_threshold": {
            str(r["threshold"]): r["ap_percent"]
            for r in global_results
        },
    }

    with (run_dir / "global_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    write_csv(
        run_dir / "ap_by_threshold.csv",
        ["threshold", "ap_percent"],
        (
            {"threshold": r["threshold"], "ap_percent": r["ap_percent"]}
            for r in global_results
        ),
    )

    write_csv(
        run_dir / "sequence_summary.csv",
        list(sequence_rows[0].keys()),
        sequence_rows,
    )

    frame_rows = global_report["per_frame"]
    if frame_rows:
        write_csv(
            run_dir / f"per_frame_metrics_at_{args.report_threshold}px.csv",
            list(frame_rows[0].keys()),
            frame_rows,
        )

    if missing_rows:
        write_csv(
            run_dir / "missing_predictions.csv",
            ["sequence_id", "missing_prediction_file"],
            missing_rows,
        )

    save_curve(
        run_dir / "global_ap_curve.png",
        global_results,
        "DroneCrowd Global Localization AP",
    )

    print("\n" + "=" * 70)
    print("评测完成")
    print(f"序列数：{summary['sequence_count']}")
    print(f"帧数：{summary['evaluated_frame_count']}")
    print(f"Global AP@1:25：{summary['global_ap_1_25_percent']:.4f}%")
    print(f"Macro AP@1:25：{summary['macro_sequence_ap_1_25_percent']:.4f}%")
    print(
        f"AP@{args.report_threshold}px："
        f"{global_report['ap_percent']:.4f}%"
    )
    print(
        f"Precision/Recall/F1："
        f"{global_report['precision']:.4f}/"
        f"{global_report['recall']:.4f}/"
        f"{global_report['f1']:.4f}"
    )
    print(
        f"TP/FP/FN："
        f"{global_report['tp']}/"
        f"{global_report['fp']}/"
        f"{global_report['fn']}"
    )
    print("输出目录：", run_dir)
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"\n评测失败：{exc}", file=sys.stderr)
        sys.exit(1)
