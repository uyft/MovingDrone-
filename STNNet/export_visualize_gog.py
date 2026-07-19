#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DroneCrowd 官方 GOG 轨迹结果导出与可视化

用途
----
读取原始 MATLAB/Octave GOG 输出文件：
    frame_id, track_id, x, y, width, height, score, label, -1, -1

生成：
1. GOG 跟踪视频（轨迹框、track_id、历史轨迹线）；
2. tracks.json（供 Java / Vue 使用）；
3. track_summary.csv（每条轨迹汇总）；
4. per_frame_tracks.csv（逐帧轨迹明细）；
5. summary.json（总体统计）。

重要说明
--------
本程序不会重新关联轨迹，也不会修改 GOG 结果。
它只读取官方 00011_GOG.txt 并进行格式转换和可视化，
因此最终轨迹仍然是原始 GOG 产生的轨迹。

示例
----
# 序列 011
python export_visualize_gog.py --seq 11

# 保存每帧可视化图片
python export_visualize_gog.py --seq 11 --save-frames

# 修改视频帧率和轨迹尾迹长度
python export_visualize_gog.py --seq 11 --fps 15 --trail-length 30
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


def resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (root / path).resolve()


def load_gog_result(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(f"找不到 GOG 结果文件：{path}")

    if path.stat().st_size == 0:
        raise ValueError(f"GOG 结果文件为空：{path}")

    try:
        data = np.loadtxt(str(path), delimiter=",", dtype=np.float64)
    except ValueError:
        data = np.loadtxt(str(path), dtype=np.float64)

    if data.ndim == 1:
        data = data.reshape(1, -1)

    if data.shape[1] < 7:
        raise ValueError(
            f"GOG 文件至少应有 7 列，实际形状为 {data.shape}"
        )

    # 仅保留前 10 列，兼容意外附加列。
    return data[:, : min(10, data.shape[1])]


def build_track_maps(data: np.ndarray):
    by_frame: dict[int, list[dict]] = defaultdict(list)
    by_track: dict[int, list[dict]] = defaultdict(list)

    for row in data:
        frame_id = int(row[0])
        track_id = int(row[1])
        x = float(row[2])
        y = float(row[3])
        width = float(row[4])
        height = float(row[5])
        score = float(row[6])

        center_x = x + width / 2.0
        center_y = y + height / 2.0

        item = {
            "frameId": frame_id,
            "trackId": track_id,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "centerX": center_x,
            "centerY": center_y,
            "score": score,
        }

        by_frame[frame_id].append(item)
        by_track[track_id].append(item)

    for track_id in by_track:
        by_track[track_id].sort(key=lambda item: item["frameId"])

    return by_frame, by_track


def track_color(track_id: int) -> tuple[int, int, int]:
    """
    根据轨迹 ID 生成稳定颜色（OpenCV BGR）。
    """
    hue = (track_id * 37) % 180
    hsv = np.uint8([[[hue, 220, 255]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


def path_metrics(points: list[dict]) -> dict:
    if not points:
        return {
            "pathLength": 0.0,
            "displacement": 0.0,
            "averageSpeed": 0.0,
        }

    path_length = 0.0

    for previous, current in zip(points[:-1], points[1:]):
        path_length += math.hypot(
            current["centerX"] - previous["centerX"],
            current["centerY"] - previous["centerY"],
        )

    displacement = math.hypot(
        points[-1]["centerX"] - points[0]["centerX"],
        points[-1]["centerY"] - points[0]["centerY"],
    )

    frame_span = max(
        1,
        points[-1]["frameId"] - points[0]["frameId"],
    )
    average_speed = path_length / frame_span

    return {
        "pathLength": path_length,
        "displacement": displacement,
        "averageSpeed": average_speed,
    }


def export_tracks_json(
    output_path: Path,
    sequence_id: int,
    by_track: dict[int, list[dict]],
) -> None:
    tracks = []

    for track_id in sorted(by_track):
        points = by_track[track_id]
        metrics = path_metrics(points)

        tracks.append(
            {
                "trackId": track_id,
                "length": len(points),
                "startFrame": points[0]["frameId"],
                "endFrame": points[-1]["frameId"],
                "meanScore": float(
                    np.mean([point["score"] for point in points])
                ),
                **metrics,
                "points": [
                    {
                        "frameId": point["frameId"],
                        "x": point["centerX"],
                        "y": point["centerY"],
                        "boxX": point["x"],
                        "boxY": point["y"],
                        "width": point["width"],
                        "height": point["height"],
                        "score": point["score"],
                    }
                    for point in points
                ],
            }
        )

    payload = {
        "sequenceId": sequence_id,
        "trackCount": len(tracks),
        "observationCount": sum(track["length"] for track in tracks),
        "tracks": tracks,
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def export_track_summary(
    output_path: Path,
    by_track: dict[int, list[dict]],
) -> None:
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
        "path_length",
        "displacement",
        "average_speed",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for track_id in sorted(by_track):
            points = by_track[track_id]
            metrics = path_metrics(points)

            writer.writerow(
                {
                    "track_id": track_id,
                    "length": len(points),
                    "start_frame": points[0]["frameId"],
                    "end_frame": points[-1]["frameId"],
                    "mean_score": float(
                        np.mean([point["score"] for point in points])
                    ),
                    "start_x": points[0]["centerX"],
                    "start_y": points[0]["centerY"],
                    "end_x": points[-1]["centerX"],
                    "end_y": points[-1]["centerY"],
                    "path_length": metrics["pathLength"],
                    "displacement": metrics["displacement"],
                    "average_speed": metrics["averageSpeed"],
                }
            )


def export_per_frame_csv(
    output_path: Path,
    by_frame: dict[int, list[dict]],
) -> None:
    fieldnames = [
        "frame_id",
        "track_id",
        "x",
        "y",
        "width",
        "height",
        "center_x",
        "center_y",
        "score",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for frame_id in sorted(by_frame):
            for item in sorted(
                by_frame[frame_id],
                key=lambda value: value["trackId"],
            ):
                writer.writerow(
                    {
                        "frame_id": frame_id,
                        "track_id": item["trackId"],
                        "x": item["x"],
                        "y": item["y"],
                        "width": item["width"],
                        "height": item["height"],
                        "center_x": item["centerX"],
                        "center_y": item["centerY"],
                        "score": item["score"],
                    }
                )


def draw_information_panel(
    image: np.ndarray,
    sequence_id: int,
    frame_id: int,
    current_track_count: int,
    total_track_count: int,
) -> None:
    overlay = image.copy()

    x0, y0 = 20, 20
    x1, y1 = 520, 160

    cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.60, image, 0.40, 0, image)

    lines = [
        f"Sequence: {sequence_id:03d}",
        f"Frame: {frame_id:03d}",
        f"Current tracks: {current_track_count}",
        f"Total GOG tracks: {total_track_count}",
    ]

    for index, line in enumerate(lines):
        cv2.putText(
            image,
            line,
            (x0 + 20, y0 + 34 + index * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )


def create_video(
    sequence_id: int,
    images_dir: Path,
    output_path: Path,
    frames_output_dir: Path,
    by_frame: dict[int, list[dict]],
    by_track: dict[int, list[dict]],
    fps: float,
    trail_length: int,
    save_frames: bool,
) -> int:
    frame_ids = sorted(by_frame)

    if not frame_ids:
        raise ValueError("GOG 结果中没有任何帧")

    first_image_path = (
        images_dir / f"img{sequence_id:03d}{frame_ids[0]:03d}.jpg"
    )
    first_image = cv2.imread(str(first_image_path))

    if first_image is None:
        raise FileNotFoundError(f"无法读取图片：{first_image_path}")

    height, width = first_image.shape[:2]

    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    if not writer.isOpened():
        raise RuntimeError(
            f"无法创建视频文件：{output_path}，"
            "请检查 OpenCV 的 mp4v 编码支持"
        )

    if save_frames:
        frames_output_dir.mkdir(parents=True, exist_ok=True)

    # 用于保存每条轨迹截至当前帧的历史中心点。
    history: dict[int, list[tuple[int, int]]] = defaultdict(list)

    written_frames = 0

    try:
        for index, frame_id in enumerate(frame_ids, start=1):
            image_path = (
                images_dir
                / f"img{sequence_id:03d}{frame_id:03d}.jpg"
            )
            image = cv2.imread(str(image_path))

            if image is None:
                raise FileNotFoundError(f"无法读取图片：{image_path}")

            current_items = by_frame.get(frame_id, [])

            for item in current_items:
                track_id = item["trackId"]
                color = track_color(track_id)

                x1 = int(round(item["x"]))
                y1 = int(round(item["y"]))
                x2 = int(round(item["x"] + item["width"]))
                y2 = int(round(item["y"] + item["height"]))

                center = (
                    int(round(item["centerX"])),
                    int(round(item["centerY"])),
                )

                history[track_id].append(center)

                if trail_length > 0:
                    history[track_id] = history[track_id][-trail_length:]

                points = history[track_id]

                if len(points) >= 2:
                    cv2.polylines(
                        image,
                        [np.asarray(points, dtype=np.int32)],
                        False,
                        color,
                        2,
                        cv2.LINE_AA,
                    )

                    # 在轨迹末端添加方向箭头。
                    cv2.arrowedLine(
                        image,
                        points[-2],
                        points[-1],
                        color,
                        2,
                        cv2.LINE_AA,
                        tipLength=0.35,
                    )

                cv2.rectangle(
                    image,
                    (x1, y1),
                    (x2, y2),
                    color,
                    2,
                )

                cv2.circle(
                    image,
                    center,
                    3,
                    color,
                    -1,
                )

                cv2.putText(
                    image,
                    f"ID {track_id}",
                    (x1, max(18, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.47,
                    color,
                    1,
                    cv2.LINE_AA,
                )

            draw_information_panel(
                image=image,
                sequence_id=sequence_id,
                frame_id=frame_id,
                current_track_count=len(current_items),
                total_track_count=len(by_track),
            )

            writer.write(image)
            written_frames += 1

            if save_frames:
                output_frame_path = (
                    frames_output_dir
                    / f"img{sequence_id:03d}{frame_id:03d}_gog.jpg"
                )
                cv2.imwrite(str(output_frame_path), image)

            if index == 1 or index % 25 == 0 or index == len(frame_ids):
                print(
                    f"生成视频：{index}/{len(frame_ids)} 帧"
                )
    finally:
        writer.release()

    return written_frames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="导出并可视化 DroneCrowd 官方 GOG 轨迹"
    )

    parser.add_argument(
        "--seq",
        type=int,
        required=True,
        help="序列编号，例如 11",
    )
    parser.add_argument(
        "--gog-file",
        type=Path,
        default=None,
        help="GOG 结果文件；默认自动定位",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=Path("../dataset/test_data/images"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation_output/gog_tracking"),
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=15.0,
    )
    parser.add_argument(
        "--trail-length",
        type=int,
        default=30,
        help="每条轨迹显示最近多少帧的尾迹；0表示不画尾迹",
    )
    parser.add_argument(
        "--save-frames",
        action="store_true",
        help="同时保存逐帧可视化图片",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script_root = Path(__file__).resolve().parent
    sequence_id = args.seq

    images_dir = resolve_path(script_root, args.images_dir)

    if args.gog_file is None:
        gog_file = (
            script_root
            / "results"
            / "tracking"
            / "cyc_pts"
            / f"{sequence_id:05d}_GOG.txt"
        ).resolve()
    else:
        gog_file = resolve_path(script_root, args.gog_file)

    base_output = resolve_path(script_root, args.output_dir)
    output_dir = base_output / f"sequence_{sequence_id:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)

    video_path = (
        output_dir
        / f"sequence_{sequence_id:03d}_GOG_tracking.mp4"
    )
    tracks_json_path = output_dir / "tracks.json"
    track_summary_path = output_dir / "track_summary.csv"
    per_frame_path = output_dir / "per_frame_tracks.csv"
    summary_path = output_dir / "summary.json"
    frames_output_dir = output_dir / "frames"

    print("=" * 72)
    print("DroneCrowd 官方 GOG 轨迹导出与可视化")
    print("序列：", f"{sequence_id:03d}")
    print("GOG文件：", gog_file)
    print("图片目录：", images_dir)
    print("输出目录：", output_dir)
    print("=" * 72)

    data = load_gog_result(gog_file)
    by_frame, by_track = build_track_maps(data)

    export_tracks_json(
        tracks_json_path,
        sequence_id,
        by_track,
    )
    export_track_summary(
        track_summary_path,
        by_track,
    )
    export_per_frame_csv(
        per_frame_path,
        by_frame,
    )

    written_frames = create_video(
        sequence_id=sequence_id,
        images_dir=images_dir,
        output_path=video_path,
        frames_output_dir=frames_output_dir,
        by_frame=by_frame,
        by_track=by_track,
        fps=args.fps,
        trail_length=args.trail_length,
        save_frames=args.save_frames,
    )

    track_lengths = [len(points) for points in by_track.values()]

    summary = {
        "sequenceId": sequence_id,
        "frameCount": written_frames,
        "trackCount": len(by_track),
        "observationCount": int(len(data)),
        "minimumTrackLength": int(min(track_lengths)),
        "maximumTrackLength": int(max(track_lengths)),
        "meanTrackLength": float(np.mean(track_lengths)),
        "videoPath": str(video_path),
        "tracksJsonPath": str(tracks_json_path),
        "trackSummaryCsvPath": str(track_summary_path),
        "perFrameCsvPath": str(per_frame_path),
    }

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 72)
    print("导出完成")
    print("轨迹数量：", len(by_track))
    print("轨迹观测数：", len(data))
    print("视频：", video_path)
    print("Java JSON：", tracks_json_path)
    print("轨迹汇总：", track_summary_path)
    print("逐帧明细：", per_frame_path)
    print("总体统计：", summary_path)
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except (
        FileNotFoundError,
        ValueError,
        RuntimeError,
        OSError,
    ) as error:
        print(f"\n处理失败：{error}", file=sys.stderr)
        sys.exit(1)
