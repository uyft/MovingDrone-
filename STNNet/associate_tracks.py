#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DroneCrowd 通用 Python 轨迹关联程序

用途
----
把 STNNet 每帧输出的定位点：
    x y confidence

关联成带 track_id 的连续轨迹，并输出：
1. 官方 DroneCrowd-MOT-toolkit 兼容 TXT；
2. Java 可视化可直接使用的 JSON；
3. 轨迹摘要 CSV。

说明
----
本程序使用“常速度预测 + 匈牙利算法 + 距离门控”进行关联。
它能替代 MATLAB 工具包中的“逐帧点 -> 连续轨迹”功能，
但不是 GOG 图优化器的逐行等价移植，因此轨迹数值不会与 GOG
做到逐点完全相同。后续的 Python MOT 评价程序可严格复现
官方 evaluateTrackA.m 的轨迹 AP 计算规则。

官方兼容结果格式（10列）
------------------------
frame_id, track_id, x, y, width, height, score, label, -1, -1

其中：
- x、y 是 20×20 框的左上角；
- score 是该检测点原始置信度；
- label 固定为 1；
- 默认移除长度小于 45 帧的轨迹，与官方 runTrackerAllClass.m 一致。

示例
----
# 当前序列 011
python associate_tracks.py --seqs 11

# 多个序列
python associate_tracks.py --seqs 11 15 21

# 全部测试序列
python associate_tracks.py --all

# 推理结果还没全部跑完，只关联已有帧
python associate_tracks.py --all --allow-partial

# 调参示例
python associate_tracks.py --seqs 11 --max-distance 30 --max-age 2 --min-track-length 45
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment


IMAGE_PATTERN = re.compile(
    r"^img(?P<sequence>\d{3})(?P<frame>\d{3})\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)


@dataclass
class Observation:
    frame_id: int
    x: float
    y: float
    score: float


@dataclass
class Track:
    track_id: int
    observations: list[Observation] = field(default_factory=list)
    missed_frames: int = 0

    @property
    def last(self) -> Observation:
        return self.observations[-1]

    @property
    def length(self) -> int:
        return len(self.observations)

    @property
    def mean_score(self) -> float:
        if not self.observations:
            return 0.0
        return float(np.mean([item.score for item in self.observations]))

    def predicted_position(self, frame_id: int) -> np.ndarray:
        """
        常速度预测。只有一个观测时退化为最后位置。
        """
        last = self.last

        if len(self.observations) < 2:
            return np.array([last.x, last.y], dtype=np.float64)

        previous = self.observations[-2]
        delta_frame = max(1, last.frame_id - previous.frame_id)

        velocity = np.array(
            [
                (last.x - previous.x) / delta_frame,
                (last.y - previous.y) / delta_frame,
            ],
            dtype=np.float64,
        )

        future_gap = frame_id - last.frame_id
        return np.array([last.x, last.y], dtype=np.float64) + velocity * future_gap

    def add(self, observation: Observation) -> None:
        self.observations.append(observation)
        self.missed_frames = 0


def resolve_path(script_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (script_root / path).resolve()


def read_test_list(path: Path) -> list[int]:
    if not path.exists():
        raise FileNotFoundError(f"找不到测试序列列表：{path}")

    values = np.loadtxt(str(path), dtype=np.int64)
    values = np.atleast_1d(values).reshape(-1)
    result = [int(value) for value in values]

    if not result:
        raise ValueError(f"测试序列列表为空：{path}")

    return result


def discover_frame_ids(image_dir: Path, sequence_id: int) -> list[int]:
    frame_ids: list[int] = []

    for path in image_dir.glob(f"img{sequence_id:03d}*"):
        match = IMAGE_PATTERN.match(path.name)
        if not match:
            continue

        if int(match.group("sequence")) != sequence_id:
            continue

        frame_ids.append(int(match.group("frame")))

    return sorted(set(frame_ids))


def load_detections(path: Path, score_threshold: float) -> np.ndarray:
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
            f"实际形状为 {data.shape}"
        )

    # 官方脚本仅保留 score > 0；这里允许用户设置更高阈值。
    data = data[data[:, 2] > score_threshold]

    if not len(data):
        return np.empty((0, 3), dtype=np.float64)

    return data


def associate_sequence(
    sequence_id: int,
    frame_ids: list[int],
    prediction_root: Path,
    max_distance: float,
    max_age: int,
    score_threshold: float,
    allow_partial: bool,
) -> tuple[list[Track], int]:
    """
    使用常速度预测 + 匈牙利匹配进行轨迹关联。
    """
    active_tracks: list[Track] = []
    finished_tracks: list[Track] = []
    next_track_id = 1
    missing_files = 0

    for index, frame_id in enumerate(frame_ids, start=1):
        prediction_path = (
            prediction_root
            / f"img{sequence_id:03d}{frame_id:03d}_loc.txt"
        )

        if not prediction_path.exists():
            missing_files += 1

            if not allow_partial:
                raise FileNotFoundError(
                    f"缺少预测文件：{prediction_path}。"
                    "中途测试可以加 --allow-partial。"
                )

            detections = np.empty((0, 3), dtype=np.float64)
        else:
            detections = load_detections(
                prediction_path,
                score_threshold=score_threshold,
            )

        # 先移除已经超龄的轨迹。
        still_active: list[Track] = []
        for track in active_tracks:
            if frame_id - track.last.frame_id > max_age + 1:
                finished_tracks.append(track)
            else:
                still_active.append(track)
        active_tracks = still_active

        matched_track_indices: set[int] = set()
        matched_detection_indices: set[int] = set()

        if active_tracks and len(detections):
            predicted_positions = np.vstack(
                [track.predicted_position(frame_id) for track in active_tracks]
            )
            detection_positions = detections[:, :2]

            cost = np.linalg.norm(
                predicted_positions[:, None, :]
                - detection_positions[None, :, :],
                axis=2,
            )

            # 相隔帧数越大，允许的位移适度增加。
            gate = np.array(
                [
                    max_distance
                    * max(1.0, math.sqrt(frame_id - track.last.frame_id))
                    for track in active_tracks
                ],
                dtype=np.float64,
            )[:, None]

            gated_cost = cost.copy()
            gated_cost[cost > gate] = 1e9

            row_indices, column_indices = linear_sum_assignment(gated_cost)

            for track_index, detection_index in zip(
                row_indices.tolist(),
                column_indices.tolist(),
            ):
                if gated_cost[track_index, detection_index] >= 1e9:
                    continue

                row = detections[detection_index]

                active_tracks[track_index].add(
                    Observation(
                        frame_id=frame_id,
                        x=float(row[0]),
                        y=float(row[1]),
                        score=float(row[2]),
                    )
                )

                matched_track_indices.add(track_index)
                matched_detection_indices.add(detection_index)

        # 未匹配轨迹增加丢失计数。
        for track_index, track in enumerate(active_tracks):
            if track_index not in matched_track_indices:
                track.missed_frames += 1

        # 未匹配检测创建新轨迹。
        for detection_index, row in enumerate(detections):
            if detection_index in matched_detection_indices:
                continue

            new_track = Track(track_id=next_track_id)
            new_track.add(
                Observation(
                    frame_id=frame_id,
                    x=float(row[0]),
                    y=float(row[1]),
                    score=float(row[2]),
                )
            )
            active_tracks.append(new_track)
            next_track_id += 1

        if index == 1 or index % 25 == 0 or index == len(frame_ids):
            print(
                f"序列 {sequence_id:03d}："
                f"{index}/{len(frame_ids)} 帧，"
                f"活动轨迹 {len(active_tracks)}"
            )

    finished_tracks.extend(active_tracks)
    return finished_tracks, missing_files


def renumber_and_filter_tracks(
    tracks: list[Track],
    min_track_length: int,
) -> list[Track]:
    kept = [track for track in tracks if track.length >= min_track_length]

    # 为官方结果重新连续编号。
    kept.sort(key=lambda track: (track.observations[0].frame_id, track.track_id))

    for new_id, track in enumerate(kept, start=1):
        track.track_id = new_id

    return kept


def write_official_txt(
    path: Path,
    tracks: list[Track],
    box_size: float,
) -> int:
    """
    输出10列：
    frame, track_id, x, y, width, height, score, label, -1, -1
    """
    rows: list[list[float]] = []
    half = box_size / 2.0

    for track in tracks:
        for observation in track.observations:
            rows.append(
                [
                    observation.frame_id,
                    track.track_id,
                    observation.x - half,
                    observation.y - half,
                    box_size,
                    box_size,
                    observation.score,
                    1,
                    -1,
                    -1,
                ]
            )

    rows.sort(key=lambda item: (item[0], item[1]))

    if rows:
        np.savetxt(
            str(path),
            np.asarray(rows, dtype=np.float64),
            fmt=[
                "%d",
                "%d",
                "%.6f",
                "%.6f",
                "%.6f",
                "%.6f",
                "%.12g",
                "%d",
                "%d",
                "%d",
            ],
        )
    else:
        path.write_text("", encoding="utf-8")

    return len(rows)


def write_tracks_json(path: Path, sequence_id: int, tracks: list[Track]) -> None:
    payload = {
        "sequenceId": sequence_id,
        "trackCount": len(tracks),
        "tracks": [
            {
                "trackId": track.track_id,
                "length": track.length,
                "startFrame": track.observations[0].frame_id,
                "endFrame": track.observations[-1].frame_id,
                "meanScore": track.mean_score,
                "points": [
                    {
                        "frameId": item.frame_id,
                        "x": item.x,
                        "y": item.y,
                        "score": item.score,
                    }
                    for item in track.observations
                ],
            }
            for track in tracks
        ],
    }

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_track_summary(path: Path, tracks: list[Track]) -> None:
    fieldnames = [
        "track_id",
        "length",
        "start_frame",
        "end_frame",
        "mean_score",
        "start_x",
        "start_y",
        "end_x",
        "end_y",
        "displacement",
    ]

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for track in tracks:
            start = track.observations[0]
            end = track.observations[-1]
            displacement = math.hypot(end.x - start.x, end.y - start.y)

            writer.writerow(
                {
                    "track_id": track.track_id,
                    "length": track.length,
                    "start_frame": start.frame_id,
                    "end_frame": end.frame_id,
                    "mean_score": track.mean_score,
                    "start_x": start.x,
                    "start_y": start.y,
                    "end_x": end.x,
                    "end_y": end.y,
                    "displacement": displacement,
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DroneCrowd 通用 Python 轨迹关联程序"
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        action="store_true",
        help="处理 testlist.txt 中全部测试序列",
    )
    group.add_argument(
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
        "--test-list",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation_output/tracking"),
    )
    parser.add_argument(
        "--tracker-name",
        type=str,
        default="PythonHungarian",
        help="输出文件中的跟踪器名称",
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=30.0,
        help="相邻帧最大关联距离，默认30像素",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=2,
        help="轨迹最多允许连续丢失多少帧，默认2",
    )
    parser.add_argument(
        "--min-track-length",
        type=int,
        default=45,
        help="保留轨迹的最短帧数，默认45（与官方一致）",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.0,
        help="仅保留置信度大于该值的检测",
    )
    parser.add_argument(
        "--box-size",
        type=float,
        default=20.0,
        help="官方兼容输出框尺寸，默认20",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="允许缺失预测帧",
    )

    return parser.parse_args()


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
    sequence_ids = args.seqs if args.seqs else official_sequences

    image_dir = dataset_root / "test_data" / "images"

    print("=" * 72)
    print("DroneCrowd Python 轨迹关联")
    print("预测目录：", prediction_root)
    print("输出目录：", output_root)
    print("序列：", sequence_ids)
    print("最大关联距离：", args.max_distance)
    print("最大丢失帧数：", args.max_age)
    print("最短轨迹长度：", args.min_track_length)
    print("=" * 72)

    global_rows: list[dict] = []

    for sequence_index, sequence_id in enumerate(sequence_ids, start=1):
        print(
            f"\n[{sequence_index}/{len(sequence_ids)}] "
            f"处理序列 {sequence_id:03d}"
        )

        frame_ids = discover_frame_ids(image_dir, sequence_id)
        if not frame_ids:
            raise FileNotFoundError(
                f"序列 {sequence_id:03d} 没有找到测试图片"
            )

        all_tracks, missing_count = associate_sequence(
            sequence_id=sequence_id,
            frame_ids=frame_ids,
            prediction_root=prediction_root,
            max_distance=args.max_distance,
            max_age=args.max_age,
            score_threshold=args.score_threshold,
            allow_partial=args.allow_partial,
        )

        kept_tracks = renumber_and_filter_tracks(
            all_tracks,
            min_track_length=args.min_track_length,
        )

        sequence_output = output_root / f"sequence_{sequence_id:03d}"
        sequence_output.mkdir(parents=True, exist_ok=True)

        official_txt = (
            sequence_output
            / f"{sequence_id:05d}_{args.tracker_name}.txt"
        )
        tracks_json = sequence_output / "tracks.json"
        summary_csv = sequence_output / "track_summary.csv"

        observation_count = write_official_txt(
            official_txt,
            kept_tracks,
            box_size=args.box_size,
        )
        write_tracks_json(tracks_json, sequence_id, kept_tracks)
        write_track_summary(summary_csv, kept_tracks)

        summary = {
            "sequence_id": sequence_id,
            "frame_count": len(frame_ids),
            "raw_track_count": len(all_tracks),
            "kept_track_count": len(kept_tracks),
            "observation_count": observation_count,
            "missing_prediction_files": missing_count,
            "min_track_length": args.min_track_length,
            "max_distance": args.max_distance,
            "max_age": args.max_age,
            "official_result_path": str(official_txt),
            "tracks_json_path": str(tracks_json),
        }
        global_rows.append(summary)

        print("原始轨迹数：", len(all_tracks))
        print("保留轨迹数：", len(kept_tracks))
        print("轨迹观测点数：", observation_count)
        print("官方兼容结果：", official_txt)
        print("Java轨迹JSON：", tracks_json)

    summary_path = output_root / "tracking_association_summary.csv"

    with summary_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=list(global_rows[0].keys()))
        writer.writeheader()
        writer.writerows(global_rows)

    print("\n" + "=" * 72)
    print("轨迹关联完成")
    print("汇总文件：", summary_path)
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"\n轨迹关联失败：{error}", file=sys.stderr)
        sys.exit(1)
