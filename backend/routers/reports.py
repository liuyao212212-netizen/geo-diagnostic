"""
报告生成路由 + 审核工作流
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import aiosqlite
import json
from datetime import datetime

from database import get_db
from services.report_generator import ReportGenerator
from services.analyzer import Analyzer

router = APIRouter()


class ReviewAction(BaseModel):
    """审核操作"""
    action: str  # approve / reject
    note: Optional[str] = ""


@router.get("/{task_id}/html")
async def generate_html_report(task_id: str):
    """生成 HTML 格式诊断报告"""
    db = await get_db()
    db.row_factory = aiosqlite.Row

    # 先获取任务和分析数据
    cursor = await db.execute("SELECT * FROM diagnostic_tasks WHERE id = ?", (task_id,))
    task = await cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task = dict(task)
    for key in ("brand_aliases", "scenarios", "platforms", "competitors", "discovered_competitors"):
        if isinstance(task[key], str):
            task[key] = json.loads(task[key])

    cursor = await db.execute(
        "SELECT * FROM query_results WHERE task_id = ?", (task_id,)
    )
    results = [dict(r) for r in await cursor.fetchall()]

    if not results:
        raise HTTPException(status_code=400, detail="该任务暂无查询结果")

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

    results_map = {r["id"]: r for r in results}
    mentions_by_result = {}
    for m in mentions:
        mentions_by_result.setdefault(m["query_result_id"], []).append(m)
    citations_by_result = {}
    for c in citations:
        citations_by_result.setdefault(c["query_result_id"], []).append(c)

    # 合并用户竞品 + 自动发现的竞品
    user_comps = task["competitors"]
    discovered_comps = task.get("discovered_competitors", [])
    all_competitors = list(user_comps)
    for comp in discovered_comps:
        if comp not in all_competitors:
            all_competitors.append(comp)

    # 从 brand_mentions 中也提取实际被提及的品牌（可能包含查询中动态发现的）
    mentioned_brand_names = set()
    for m_list in mentions_by_result.values():
        for m in m_list:
            mentioned_brand_names.add(m["brand_name"])

    # 最终 all_brands: 主品牌 + 合并竞品 + 实际提及但未预设的品牌
    all_brands = [task["brand_name"]]
    for b in all_competitors:
        if b not in all_brands:
            all_brands.append(b)
    for b in mentioned_brand_names:
        if b not in all_brands:
            all_brands.append(b)

    analyzer = Analyzer(
        brand_name=task["brand_name"],
        brand_aliases=task["brand_aliases"],
        competitors=all_competitors,
        all_brands=all_brands,
    )
    analysis = analyzer.analyze(results, mentions_by_result, citations_by_result)

    # 生成 HTML 报告
    generator = ReportGenerator()
    html_content = generator.generate_html(
        brand_name=task["brand_name"],
        analysis=analysis,
        task=task,
        results=results,
        discovered_competitors=discovered_comps,
    )

    return {"task_id": task_id, "html_content": html_content}


@router.post("/{task_id}/review")
async def review_report(task_id: str, body: ReviewAction):
    """
    审核报告
    action: approve（审核通过）/ reject（驳回）
    """
    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action 必须为 approve 或 reject")

    db = await get_db()
    db.row_factory = aiosqlite.Row

    cursor = await db.execute("SELECT * FROM diagnostic_tasks WHERE id = ?", (task_id,))
    task = await cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = dict(task)
    if task.get("status") != "completed":
        raise HTTPException(status_code=400, detail="只能审核已完成的任务")

    review_status = "approved" if body.action == "approve" else "rejected"
    now = datetime.now().isoformat()

    await db.execute(
        """UPDATE diagnostic_tasks
           SET review_status = ?, review_note = ?, reviewed_at = ?
           WHERE id = ?""",
        (review_status, body.note or "", now, task_id),
    )
    await db.commit()

    return {
        "task_id": task_id,
        "review_status": review_status,
        "message": "报告已审核通过" if body.action == "approve" else "报告已驳回",
    }


@router.get("/{task_id}/review-status")
async def get_review_status(task_id: str):
    """获取报告审核状态"""
    db = await get_db()
    db.row_factory = aiosqlite.Row

    cursor = await db.execute(
        "SELECT status, review_status, review_note, reviewed_at FROM diagnostic_tasks WHERE id = ?",
        (task_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")

    return dict(row)
