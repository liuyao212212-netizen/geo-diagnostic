"""
数据分析路由 - 多维分析 + 品牌得分
"""
from fastapi import APIRouter, HTTPException
import aiosqlite
import json
from datetime import datetime

from database import get_db
from services.analyzer import Analyzer

router = APIRouter()


@router.get("/{task_id}")
async def get_analysis(task_id: str):
    """获取诊断任务的完整分析结果"""
    db = await get_db()
    db.row_factory = aiosqlite.Row

    # 获取任务信息
    cursor = await db.execute("SELECT * FROM diagnostic_tasks WHERE id = ?", (task_id,))
    task = await cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task = dict(task)
    for key in ("brand_aliases", "scenarios", "platforms", "competitors"):
        if isinstance(task[key], str):
            task[key] = json.loads(task[key])

    # 获取所有查询结果和品牌提及
    cursor = await db.execute(
        "SELECT * FROM query_results WHERE task_id = ?", (task_id,)
    )
    results = [dict(r) for r in await cursor.fetchall()]

    if not results:
        raise HTTPException(status_code=400, detail="该任务暂无查询结果，请先执行查询")

    result_ids = [r["id"] for r in results]
    placeholders = ",".join("?" * len(result_ids))

    cursor = await db.execute(
        f"SELECT * FROM brand_mentions WHERE query_result_id IN ({placeholders}) ORDER BY mention_rank",
        result_ids,
    )
    mentions = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute(
        f"SELECT * FROM citation_sources WHERE query_result_id IN ({placeholders}) ORDER BY citation_rank",
        result_ids,
    )
    citations = [dict(r) for r in await cursor.fetchall()]

    # 构建结果映射
    results_map = {r["id"]: r for r in results}
    mentions_by_result = {}
    for m in mentions:
        rid = m["query_result_id"]
        mentions_by_result.setdefault(rid, []).append(m)
    citations_by_result = {}
    for c in citations:
        rid = c["query_result_id"]
        citations_by_result.setdefault(rid, []).append(c)

    # 执行分析
    analyzer = Analyzer(
        brand_name=task["brand_name"],
        brand_aliases=json.loads(task["brand_aliases"]) if isinstance(task["brand_aliases"], str) else task["brand_aliases"],
        competitors=task["competitors"],
        all_brands=[task["brand_name"]] + task["competitors"],
    )

    analysis_result = analyzer.analyze(results, mentions_by_result, citations_by_result)
    analysis_result["task_id"] = task_id
    analysis_result["generated_at"] = datetime.now().isoformat()

    return analysis_result
