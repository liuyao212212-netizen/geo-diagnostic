"""
数据模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import json
import uuid


# ============ 场景模型 ============

class Scenario(BaseModel):
    """诊断场景"""
    question: str = Field(..., description="模拟用户提问")
    category: str = Field(..., description="场景分类，如：空调、冰箱等")

    class Config:
        json_schema_extra = {
            "examples": [
                {"question": "买空调选什么牌子好？性价比高的推荐", "category": "空调"}
            ]
        }


# ============ 平台配置模型 ============

class PlatformConfig(BaseModel):
    """平台配置"""
    platform_name: str
    platform_version: str = "default"
    platform_type: str = "api"  # api / browser

    class Config:
        json_schema_extra = {
            "examples": [
                {"platform_name": "千问", "platform_version": "网页版", "platform_type": "api"}
            ]
        }


# ============ 诊断任务模型 ============

class DiagnosticTaskCreate(BaseModel):
    """创建诊断任务"""
    brand_name: str = Field(..., description="诊断品牌名称")
    brand_aliases: List[str] = Field(default_factory=list, description="品牌别名列表")
    scenarios: List[Scenario] = Field(default_factory=list, description="诊断场景列表（为空时系统自动生成）")
    platforms: List[PlatformConfig] = Field(..., min_length=1, description="目标平台列表")
    competitors: List[str] = Field(default_factory=list, description="竞品品牌列表")


class DiagnosticTaskResponse(BaseModel):
    """诊断任务响应"""
    id: str
    brand_name: str
    brand_aliases: List[str]
    scenarios: List[dict]
    platforms: List[dict]
    competitors: List[str]
    discovered_competitors: List[str] = []
    status: str
    created_at: str
    completed_at: Optional[str] = None


# ============ 查询结果模型 ============

class QueryResultResponse(BaseModel):
    """查询结果响应"""
    id: str
    task_id: str
    platform_name: str
    platform_version: str
    scenario_question: str
    scenario_category: str
    ai_response_text: Optional[str]
    query_duration_ms: Optional[int]
    queried_at: str
    error_message: Optional[str]
    brand_mentions: Optional[List[dict]] = None
    citation_sources: Optional[List[dict]] = None


# ============ 品牌提及模型 ============

class BrandMention(BaseModel):
    """品牌提及"""
    brand_name: str
    mention_rank: int
    sentiment: str  # positive / neutral / negative
    mention_context: str = ""
    is_primary_brand: bool = False


# ============ 分析结果模型 ============

class BrandScore(BaseModel):
    """品牌得分"""
    brand_name: str
    mention_rate: float  # 提及率
    avg_rank: float  # 平均排名
    positive_rate: float  # 正面情感率
    geo_score: float  # GEO 综合得分
    total_mentions: int


class PlatformBrandScore(BaseModel):
    """平台×品牌得分"""
    platform_name: str
    brand_scores: List[BrandScore]


class HeatmapData(BaseModel):
    """热力图数据"""
    platforms: List[str]
    scenarios: List[str]
    data: List[List[float]]  # [platform_index][scenario_index] = score


class AnalysisResponse(BaseModel):
    """分析结果响应"""
    task_id: str
    brand_name: str
    brand_scores: List[BrandScore]
    platform_analysis: List[PlatformBrandScore]
    heatmap: HeatmapData
    sentiment_summary: dict
    citation_summary: dict
    generated_at: str
