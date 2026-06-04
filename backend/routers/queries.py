"""
查询管理路由 - 执行查询 + 获取结果
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
import aiosqlite
import json
import asyncio
from datetime import datetime
from typing import Optional

from database import get_db
from services.query_engine import QueryEngine

router = APIRouter()

# 全局任务引用，防止被垃圾回收
_background_tasks: set = set()


async def _run_queries_in_background(task_id: str, task: dict):
    """后台执行查询任务"""
    import sys
    print(f"[后台任务] 开始执行任务 {task_id}", flush=True)
    sys.stdout.flush()
    try:
        engine = QueryEngine()
        print(f"[后台任务] QueryEngine 初始化完成，可用平台: {engine.get_available_platforms()}", flush=True)
        sys.stdout.flush()
        await engine.run_task(task)

        db = await get_db()
        now = datetime.now().isoformat()
        await db.execute(
            "UPDATE diagnostic_tasks SET status = 'completed', completed_at = ? WHERE id = ?",
            (now, task_id),
        )
        await db.commit()
        print(f"[后台任务] 任务 {task_id} 执行完成", flush=True)
    except Exception as e:
        import traceback
        print(f"[后台任务] 任务 {task_id} 执行失败: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        db = await get_db()
        await db.execute(
            "UPDATE diagnostic_tasks SET status = 'failed' WHERE id = ?", (task_id,),
        )
        await db.commit()
    finally:
        # 从全局集合中移除
        _background_tasks.discard(task_id)


@router.post("/{task_id}/run")
async def run_queries(task_id: str):
    """执行诊断任务的所有查询（立即返回，后台执行）"""
    db = await get_db()
    db.row_factory = aiosqlite.Row

    # 加载任务数据
    cursor = await db.execute("SELECT * FROM diagnostic_tasks WHERE id = ?", (task_id,))
    task = await cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = dict(task)
    for key in ("brand_aliases", "scenarios", "platforms", "competitors", "discovered_competitors"):
        if isinstance(task[key], str):
            task[key] = json.loads(task[key])

    if task["status"] == "running":
        raise HTTPException(status_code=400, detail="任务正在执行中")

    # 更新状态为 running
    await db.execute("UPDATE diagnostic_tasks SET status = 'running' WHERE id = ?", (task_id,))
    await db.commit()

    # 后台异步执行查询（避免前端超时等待）
    task_coro = _run_queries_in_background(task_id, task)
    bg_task = asyncio.create_task(task_coro)
    _background_tasks.add(task_id)
    bg_task.add_done_callback(lambda t: _background_tasks.discard(task_id))

    return {
        "status": "running",
        "task_id": task_id,
        "message": "查询任务已启动，请稍后刷新查看结果",
    }


@router.get("/{task_id}/results")
async def get_query_results(task_id: str):
    """获取任务的所有查询结果"""
    db = await get_db()
    db.row_factory = aiosqlite.Row

    # 查询结果
    cursor = await db.execute(
        """SELECT * FROM query_results WHERE task_id = ? ORDER BY queried_at""",
        (task_id,),
    )
    results = [dict(r) for r in await cursor.fetchall()]

    # 品牌提及
    if results:
        result_ids = [r["id"] for r in results]
        placeholders = ",".join("?" * len(result_ids))
        cursor = await db.execute(
            f"""SELECT * FROM brand_mentions WHERE query_result_id IN ({placeholders})
                ORDER BY query_result_id, mention_rank""",
            result_ids,
        )
        mentions = await cursor.fetchall()

        # 引用来源
        cursor = await db.execute(
            f"""SELECT * FROM citation_sources WHERE query_result_id IN ({placeholders})
                ORDER BY query_result_id, citation_rank""",
            result_ids,
        )
        citations = await cursor.fetchall()

        # 组织数据
        mentions_by_result = {}
        for m in mentions:
            m = dict(m)
            rid = m["query_result_id"]
            if rid not in mentions_by_result:
                mentions_by_result[rid] = []
            mentions_by_result[rid].append(m)

        citations_by_result = {}
        for c in citations:
            c = dict(c)
            rid = c["query_result_id"]
            if rid not in citations_by_result:
                citations_by_result[rid] = []
            citations_by_result[rid].append(c)

        for r in results:
            r["brand_mentions"] = mentions_by_result.get(r["id"], [])
            r["citation_sources"] = citations_by_result.get(r["id"], [])

    return {"task_id": task_id, "total": len(results), "results": results}


@router.get("/{task_id}/status")
async def get_task_status(task_id: str):
    """获取任务执行状态"""
    db = await get_db()
    db.row_factory = aiosqlite.Row

    cursor = await db.execute("SELECT status, completed_at FROM diagnostic_tasks WHERE id = ?", (task_id,))
    task = await cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    cursor = await db.execute(
        "SELECT COUNT(*) as total, SUM(CASE WHEN ai_response_text IS NOT NULL THEN 1 ELSE 0 END) as completed FROM query_results WHERE task_id = ?",
        (task_id,),
    )
    counts = dict(await cursor.fetchone())

    return {
        "task_id": task_id,
        "status": task["status"],
        "completed_at": task["completed_at"],
        "queries_total": counts["total"] or 0,
        "queries_completed": counts["completed"] or 0,
    }
