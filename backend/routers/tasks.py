"""
任务管理路由 - CRUD + 执行
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from database import get_db, DB_PATH
import aiosqlite
import json
import uuid
from datetime import datetime
from typing import List, Optional

from models.schemas import DiagnosticTaskCreate, DiagnosticTaskResponse, PlatformConfig

router = APIRouter()


def _row_to_dict(row: aiosqlite.Row) -> dict:
    """将数据库行转换为字典，自动解析 JSON 字段"""
    d = dict(row)
    for key in ("brand_aliases", "scenarios", "platforms", "competitors", "discovered_competitors"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = []
    return d


# ============ 平台列表（必须在 /{task_id} 之前） ============

@router.get("/platforms")
async def list_platforms():
    """获取已配置的 AI 平台列表"""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM platform_configs WHERE is_enabled = 1")
    rows = await cursor.fetchall()
    return [
        {
            "id": r["id"],
            "name": r["platform_name"],
            "type": r["platform_type"],
            "model": r["model_name"],
        }
        for r in rows
    ]


# ============ 任务 CRUD ============

@router.post("", response_model=DiagnosticTaskResponse)
async def create_task(task_data: DiagnosticTaskCreate, bg_tasks: BackgroundTasks):
    """创建新的诊断任务"""
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    db = await get_db()
    await db.execute(
        """INSERT INTO diagnostic_tasks
           (id, brand_name, brand_aliases, scenarios, platforms, competitors, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task_id,
            task_data.brand_name,
            json.dumps(task_data.brand_aliases, ensure_ascii=False),
            json.dumps([s.model_dump() for s in task_data.scenarios], ensure_ascii=False),
            json.dumps([p.model_dump() for p in task_data.platforms], ensure_ascii=False),
            json.dumps(task_data.competitors, ensure_ascii=False),
            "pending",
            now,
        ),
    )
    await db.commit()

    return DiagnosticTaskResponse(
        id=task_id,
        brand_name=task_data.brand_name,
        brand_aliases=task_data.brand_aliases,
        scenarios=[s.model_dump() for s in task_data.scenarios],
        platforms=[p.model_dump() for p in task_data.platforms],
        competitors=task_data.competitors,
        status="pending",
        created_at=now,
    )


@router.get("", response_model=List[DiagnosticTaskResponse])
async def list_tasks(limit: int = 20, offset: int = 0):
    """获取任务列表"""
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cursor = await db.execute(
        "SELECT * FROM diagnostic_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = await cursor.fetchall()

    return [_row_to_dict(r) for r in rows]


@router.get("/{task_id}", response_model=DiagnosticTaskResponse)
async def get_task(task_id: str):
    """获取单个任务详情"""
    db = await get_db()
    db.row_factory = aiosqlite.Row
    cursor = await db.execute("SELECT * FROM diagnostic_tasks WHERE id = ?", (task_id,))
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")

    return _row_to_dict(row)


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务及其关联数据"""
    db = await get_db()

    # 检查任务是否存在
    cursor = await db.execute("SELECT id FROM diagnostic_tasks WHERE id = ?", (task_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="任务不存在")

    # 级联删除关联数据
    cursor = await db.execute("SELECT id FROM query_results WHERE task_id = ?", (task_id,))
    query_ids = [r[0] for r in await cursor.fetchall()]

    if query_ids:
        placeholders = ",".join("?" * len(query_ids))
        await db.execute(f"DELETE FROM brand_mentions WHERE query_result_id IN ({placeholders})", query_ids)
        await db.execute(f"DELETE FROM citation_sources WHERE query_result_id IN ({placeholders})", query_ids)

    await db.execute("DELETE FROM query_results WHERE task_id = ?", (task_id,))
    await db.execute("DELETE FROM diagnostic_tasks WHERE id = ?", (task_id,))
    await db.commit()

    return {"status": "ok", "message": "任务已删除"}
