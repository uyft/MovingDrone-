"""
SQLite 持久化存储模块 — 同步 + 异步混合版
"""
import sqlite3
import json
import os
from datetime import datetime
from threading import Lock

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.db")
_db_lock = Lock()


def _get_sync_conn() -> sqlite3.Connection:
    """获取同步连接（供推理线程使用）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db_sync():
    """同步初始化数据库（在 startup 事件中调用）"""
    conn = _get_sync_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                progress REAL DEFAULT 0,
                message TEXT DEFAULT '',
                mode TEXT DEFAULT 'counting',
                model TEXT DEFAULT '',
                filename TEXT DEFAULT '',
                size_mb REAL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                task_id TEXT PRIMARY KEY,
                video_path TEXT,
                output_video TEXT,
                fps REAL,
                total_frames INTEGER,
                width INTEGER,
                height INTEGER,
                total_time REAL,
                frames_json TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
        """)
        conn.commit()
    finally:
        conn.close()


# ============================================================
#  同步操作（供推理线程使用）
# ============================================================

def db_create_task(task_id: str, status: str = "pending", message: str = "",
                   mode: str = "counting", model: str = "",
                   filename: str = "", size_mb: float = 0):
    with _db_lock:
        conn = _get_sync_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO tasks (task_id, status, progress, message, mode, model, filename, size_mb, created_at) "
                "VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?)",
                (task_id, status, message, mode, model, filename, size_mb, datetime.now().isoformat())
            )
            conn.commit()
        finally:
            conn.close()


def db_update_task(task_id: str, **kwargs):
    """同步更新任务字段"""
    allowed = {"status", "progress", "message", "model"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [task_id]
    with _db_lock:
        conn = _get_sync_conn()
        try:
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE task_id = ?", values)
            conn.commit()
        finally:
            conn.close()


def db_get_task(task_id: str) -> dict | None:
    with _db_lock:
        conn = _get_sync_conn()
        try:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def db_list_tasks() -> list[dict]:
    with _db_lock:
        conn = _get_sync_conn()
        try:
            rows = conn.execute(
                "SELECT t.*, r.total_frames FROM tasks t "
                "LEFT JOIN results r ON t.task_id = r.task_id "
                "ORDER BY t.created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def db_save_result(task_id: str, result: dict):
    frames = result.get("frames", [])
    slim_frames = [{"frame": f.get("frame", i), "count": f.get("count", 0),
                    "peaks": f.get("peaks", [])}
                   for i, f in enumerate(frames)]
    frames_json = json.dumps(slim_frames, ensure_ascii=False)
    with _db_lock:
        conn = _get_sync_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO results (task_id, video_path, output_video, fps, "
                "total_frames, width, height, total_time, frames_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (task_id, result.get("video_path", ""), result.get("output_video", ""),
                 result.get("fps", 0), result.get("total_frames", 0),
                 result.get("width", 0), result.get("height", 0),
                 result.get("total_time", 0), frames_json)
            )
            conn.commit()
        finally:
            conn.close()


def db_delete_task(task_id: str):
    """删除任务及其结果"""
    with _db_lock:
        conn = _get_sync_conn()
        try:
            conn.execute("DELETE FROM results WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()
        finally:
            conn.close()


def db_get_result(task_id: str) -> dict | None:
    with _db_lock:
        conn = _get_sync_conn()
        try:
            row = conn.execute("SELECT * FROM results WHERE task_id = ?", (task_id,)).fetchone()
            if row:
                result = dict(row)
                if result.get("frames_json"):
                    result["frames"] = json.loads(result["frames_json"])
                    del result["frames_json"]
                return result
        finally:
            conn.close()
    return None
