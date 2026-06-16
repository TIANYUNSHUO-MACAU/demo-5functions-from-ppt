# 历史记录服务
# 使用 SQLite 存储所有工具的生成历史

import os
import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional


DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "history.db"
)


def _ensure_db():
    """确保数据库和表已创建"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY,
            tool TEXT NOT NULL,
            title TEXT,
            input_text TEXT,
            output_text TEXT,
            meta TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tool ON history(tool)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON history(created_at DESC)")
    conn.commit()
    conn.close()


def add_record(tool: str, title: str, input_text: str, output_text: str, meta: dict = None) -> str:
    """新增一条历史记录，返回记录 ID"""
    _ensure_db()
    record_id = uuid.uuid4().hex[:12]
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO history (id, tool, title, input_text, output_text, meta, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            record_id,
            tool,
            (title or "")[:200],
            (input_text or "")[:1000],
            (output_text or "")[:50000],
            json.dumps(meta or {}, ensure_ascii=False),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()
    return record_id


def list_records(tool: str = None, limit: int = 50) -> List[Dict]:
    """列出历史记录（按时间倒序）"""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if tool:
        rows = conn.execute(
            "SELECT * FROM history WHERE tool = ? ORDER BY created_at DESC LIMIT ?",
            (tool, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_record(record_id: str) -> Optional[Dict]:
    """获取单条历史记录"""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM history WHERE id = ?", (record_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["meta"] = json.loads(d.get("meta") or "{}")
    except Exception:
        d["meta"] = {}
    return d


def delete_record(record_id: str) -> bool:
    """删除单条历史记录"""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def clear_records(tool: str = None) -> int:
    """清空历史（可按工具清空）"""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    if tool:
        cur = conn.execute("DELETE FROM history WHERE tool = ?", (tool,))
    else:
        cur = conn.execute("DELETE FROM history")
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted
