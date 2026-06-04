"""
AI 平台查询引擎 V5
4步流水线：竞品发现 → 关键词生成 → 批量查询 → 解析报告
支持千问 DashScope、DeepSeek、豆包（火山引擎）
使用 OpenAI 兼容协议统一调用
"""
import httpx
import asyncio
import json
import uuid
import time
import random
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

from config import settings
from database import get_db


class AIPlatformClient:
    """统一 AI 平台调用客户端（OpenAI 兼容协议）"""

    def __init__(
        self,
        platform_name: str,
        api_key: str,
        base_url: str,
        model: str,
        endpoint_id: Optional[str] = None,
    ):
        self.platform_name = platform_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.endpoint_id = endpoint_id

    async def query(self, question: str, system_prompt: str = "") -> tuple:
        """
        发送查询请求
        返回: (response_text, duration_ms)
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": question})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        # 火山引擎需要额外参数
        if self.endpoint_id:
            payload["model"] = self.endpoint_id

        headers = {
            "Authorization": "Bearer {0}".format(self.api_key),
            "Content-Type": "application/json",
        }

        start = time.time()
        async with httpx.AsyncClient(timeout=settings.QUERY_TIMEOUT) as client:
            resp = await client.post(
                "{0}/chat/completions".format(self.base_url),
                json=payload,
                headers=headers,
            )
            duration_ms = int((time.time() - start) * 1000)

            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]

        return text, duration_ms


class QueryEngine:
    """查询引擎 V5 - 4步流水线"""

    # 平台配置映射
    PLATFORM_REGISTRY = {
        "千问": {
            "api_key": "DASHSCOPE_API_KEY",
            "base_url": "DASHSCOPE_BASE_URL",
            "model": "DASHSCOPE_MODEL",
        },
        "DeepSeek": {
            "api_key": "DEEPSEEK_API_KEY",
            "base_url": "DEEPSEEK_BASE_URL",
            "model": "DEEPSEEK_MODEL",
        },
        "豆包": {
            "api_key": "VOLCENGINE_API_KEY",
            "base_url": "VOLCENGINE_BASE_URL",
            "model": "VOLCENGINE_MODEL",
            "endpoint_id": "VOLCENGINE_ENDPOINT_ID",
        },
    }

    def __init__(self):
        self.clients: Dict[str, AIPlatformClient] = {}
        self._init_clients()

    def _init_clients(self):
        """初始化已配置 API Key 的平台客户端"""
        for platform, config in self.PLATFORM_REGISTRY.items():
            api_key = getattr(settings, config["api_key"])
            if api_key:
                endpoint_id_key = config.get("endpoint_id", "")
                endpoint_id = getattr(settings, endpoint_id_key) if endpoint_id_key else None
                client = AIPlatformClient(
                    platform_name=platform,
                    api_key=api_key,
                    base_url=getattr(settings, config["base_url"]),
                    model=getattr(settings, config["model"]),
                    endpoint_id=endpoint_id,
                )
                self.clients[platform] = client

    def get_available_platforms(self) -> List[str]:
        """获取可用平台列表"""
        return list(self.clients.keys())

    async def run_task(self, task: dict) -> List[dict]:
        """
        执行完整的诊断任务（V5: 4步流水线）
        Step 1: 竞品自动发现（LLM直接返回JSON）
        Step 2: 关键词自动生成（LLM生成15-20个）
        Step 3: 批量查询AI平台
        Step 4: 解析 + 写入数据库
        返回所有查询结果列表
        """
        from services.parser import ResponseParser
        from services.competitor_discovery import CompetitorDiscovery
        from services.keyword_generator import KeywordGenerator
        from services.scenario_discovery import ScenarioDiscovery

        task_id = task["id"]
        brand_name = task["brand_name"]
        brand_aliases = task.get("brand_aliases", [])
        user_competitors = task.get("competitors", [])
        platforms = task["platforms"]
        scenarios = task["scenarios"]

        # 保存品牌分析结果（Step 2 关键词生成需要）
        brand_analysis = {}

        # ============ Step 1: 竞品自动发现 ============
        print(f"[Step 1] 竞品自动发现 for {brand_name}", flush=True)
        sys.stdout.flush()

        # 1a. 场景自动发现（用户未填写时）
        valid_user_scenarios = [s for s in scenarios if s.get("question", "").strip()]
        if not valid_user_scenarios:
            print(f"[Step 1a] 用户未填写场景，开始自动生成", flush=True)
            scenario_discovery = ScenarioDiscovery(brand_name, brand_aliases)
            analysis_query = scenario_discovery.generate_brand_analysis_query()

            # 用第一个可用平台分析品牌
            discovery_clients = []
            for platform_config in platforms:
                platform_name = platform_config["platform_name"]
                if platform_name in self.clients:
                    discovery_clients.append((platform_name, self.clients[platform_name]))

            if discovery_clients:
                _, analysis_client = discovery_clients[0]
                try:
                    delay = random.uniform(settings.QUERY_DELAY_MIN, settings.QUERY_DELAY_MAX)
                    await asyncio.sleep(delay)

                    analysis_prompt = (
                        "你是一个行业分析专家。请分析该品牌所在的行业信息。"
                        "严格按照要求的JSON格式回答，不要添加任何多余文字或解释。"
                    )
                    analysis_text, _ = await analysis_client.query(analysis_query, analysis_prompt)
                    brand_analysis = scenario_discovery.parse_brand_analysis(analysis_text)
                    auto_scenarios = scenario_discovery.generate_scenarios(brand_analysis)

                    scenarios = auto_scenarios
                    print(f"[Step 1a] 场景自动生成完成: {len(auto_scenarios)} 个场景", flush=True)
                    for i, s in enumerate(auto_scenarios):
                        print(f"  场景{i+1}: [{s['category']}] {s['question'][:50]}", flush=True)
                    sys.stdout.flush()

                    # 更新数据库中的 scenarios
                    db = await get_db()
                    try:
                        scenarios_for_db = [
                            {"question": s["question"], "category": s["category"]}
                            for s in auto_scenarios
                        ]
                        await db.execute(
                            "UPDATE diagnostic_tasks SET scenarios = ? WHERE id = ?",
                            (json.dumps(scenarios_for_db, ensure_ascii=False), task_id),
                        )
                        await db.commit()
                    except Exception as e:
                        print(f"[Step 1a] 更新数据库场景失败: {e}", flush=True)
                except Exception as e:
                    print(f"[Step 1a] 场景自动生成失败: {e}", flush=True)
                    scenarios = self._fallback_scenarios(brand_name)
            else:
                scenarios = self._fallback_scenarios(brand_name)

        # 1b. 竞品发现（LLM直接返回JSON）
        discovery = CompetitorDiscovery(brand_name, brand_aliases)
        discovery_query = discovery.generate_discovery_query()

        # 用第一个可用平台发现竞品
        discovery_clients = []
        for platform_config in platforms:
            platform_name = platform_config["platform_name"]
            if platform_name in self.clients:
                discovery_clients.append((platform_name, self.clients[platform_name]))

        discovered_competitors = []
        if discovery_clients:
            _, discover_client = discovery_clients[0]
            try:
                delay = random.uniform(settings.QUERY_DELAY_MIN, settings.QUERY_DELAY_MAX)
                await asyncio.sleep(delay)

                discover_prompt = (
                    "你是行业分析专家。请如实回答，不要虚构。"
                    "只返回JSON，不要加任何解释文字。"
                )
                response_text, _ = await discover_client.query(discovery_query, discover_prompt)
                discovered_competitors = CompetitorDiscovery.parse_discovery_response(response_text, brand_name)
                print(f"[Step 1b] 竞品发现完成: {discovered_competitors}", flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f"[Step 1b] 竞品发现失败: {e}", flush=True)

        # 合并用户提供的竞品 + 自动发现的竞品
        all_competitors = list(user_competitors)
        for comp in discovered_competitors:
            if comp not in all_competitors and comp != brand_name:
                all_competitors.append(comp)

        print(f"[Step 1] 完成: 用户填写 {len(user_competitors)} 个, "
              f"自动发现 {len(discovered_competitors)} 个, "
              f"合并后 {len(all_competitors)} 个", flush=True)
        print(f"[Step 1] 全部竞品: {all_competitors}", flush=True)
        sys.stdout.flush()

        # 更新数据库
        db = await get_db()
        try:
            await db.execute(
                "UPDATE diagnostic_tasks SET discovered_competitors = ? WHERE id = ?",
                (json.dumps(discovered_competitors, ensure_ascii=False), task_id),
            )
            await db.commit()
        except Exception:
            pass

        # ============ Step 2: 关键词自动生成 ============
        print(f"[Step 2] 关键词自动生成", flush=True)
        sys.stdout.flush()

        # 从品牌分析结果获取行业（Step 1a 已完成）
        industry = brand_analysis.get("industry", "相关领域") if brand_analysis else "相关领域"

        keyword_gen = KeywordGenerator(brand_name, industry, all_competitors)
        keyword_query = keyword_gen.generate_keyword_query()

        generated_keywords = []
        if discovery_clients:
            _, keyword_client = discovery_clients[0]
            try:
                delay = random.uniform(settings.QUERY_DELAY_MIN, settings.QUERY_DELAY_MAX)
                await asyncio.sleep(delay)

                keyword_prompt = (
                    "你是消费者搜索行为分析专家。"
                    "只返回JSON，不要加任何解释文字。"
                )
                response_text, _ = await keyword_client.query(keyword_query, keyword_prompt)
                generated_keywords = KeywordGenerator.parse_keyword_response(response_text)
                print(f"[Step 2] 关键词生成完成: {len(generated_keywords)} 个", flush=True)
                for i, kw in enumerate(generated_keywords[:5]):
                    print(f"  关键词{i+1}: [{kw['dimension']}] {kw['keyword'][:50]}", flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f"[Step 2] 关键词生成失败: {e}", flush=True)

        # 如果关键词生成失败，从场景中提取问题作为关键词
        if not generated_keywords:
            generated_keywords = [
                {"keyword": s["question"], "dimension": s.get("category", "category")}
                for s in scenarios
            ]
            print(f"[Step 2] 使用场景作为关键词: {len(generated_keywords)} 个", flush=True)

        # ============ Step 3: 批量查询 AI 平台 ============
        print(f"[Step 3] 开始批量查询，{len(generated_keywords)} 关键词 × {len(platforms)} 平台", flush=True)
        sys.stdout.flush()

        # 使用合并后的竞品列表初始化解析器
        parser = ResponseParser(
            brand_name=brand_name,
            brand_aliases=brand_aliases,
            competitors=all_competitors,
        )

        results = []

        # 构建 system prompt
        system_prompt = (
            "你是一个客观中立的助手。"
            "请根据用户的提问，给出真实、客观的回答。"
            "如果涉及品牌推荐或比较，请尽量说明提及的原因。"
        )

        # 扁平化：平台 × 场景（使用生成的关键词作为问题）
        for platform_config in platforms:
            platform_name = platform_config["platform_name"]
            platform_version = platform_config.get("platform_version", "default")

            if platform_name not in self.clients:
                results.append({
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "platform_name": platform_name,
                    "platform_version": platform_version,
                    "scenario_question": "",
                    "scenario_category": "",
                    "ai_response_text": None,
                    "query_duration_ms": None,
                    "error": "平台 {0} 未配置 API Key".format(platform_name),
                })
                continue

            client = self.clients[platform_name]

            for kw in generated_keywords:
                question = kw["keyword"]
                category = kw.get("dimension", "category")

                try:
                    # 随机延迟，避免频率过高
                    delay = random.uniform(settings.QUERY_DELAY_MIN, settings.QUERY_DELAY_MAX)
                    await asyncio.sleep(delay)

                    # 发送查询
                    response_text, duration_ms = await client.query(question, system_prompt)

                    # 解析结果
                    mentions, citations = parser.parse(response_text)

                    result = {
                        "id": str(uuid.uuid4()),
                        "task_id": task_id,
                        "platform_name": platform_name,
                        "platform_version": platform_version,
                        "scenario_question": question,
                        "scenario_category": category,
                        "ai_response_text": response_text,
                        "query_duration_ms": duration_ms,
                        "mentions": mentions,
                        "citations": citations,
                        "error": None,
                    }
                except Exception as e:
                    result = {
                        "id": str(uuid.uuid4()),
                        "task_id": task_id,
                        "platform_name": platform_name,
                        "platform_version": platform_version,
                        "scenario_question": question,
                        "scenario_category": category,
                        "ai_response_text": None,
                        "query_duration_ms": None,
                        "error": str(e),
                    }

                results.append(result)

                # 实时写入数据库
                await self._write_result_to_db(db, result)
                await db.commit()

        # ============ Step 4: 完成 ============
        print(f"[Step 4] 查询完成，共 {len(results)} 个结果", flush=True)
        sys.stdout.flush()

        return results

    async def _write_result_to_db(self, db, result: dict):
        """将单个查询结果写入数据库"""
        await db.execute(
            """INSERT INTO query_results
               (id, task_id, platform_name, platform_version, scenario_question,
                scenario_category, ai_response_text, query_duration_ms, queried_at, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result["id"],
                result["task_id"],
                result["platform_name"],
                result["platform_version"],
                result["scenario_question"],
                result["scenario_category"],
                result.get("ai_response_text"),
                result.get("query_duration_ms"),
                datetime.now().isoformat(),
                result.get("error"),
            ),
        )

        # 写入品牌提及
        for mention in result.get("mentions", []):
            await db.execute(
                """INSERT INTO brand_mentions
                   (id, query_result_id, brand_name, mention_rank, sentiment, mention_context, is_primary_brand)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    result["id"],
                    mention["brand_name"],
                    mention["mention_rank"],
                    mention["sentiment"],
                    mention.get("mention_context", ""),
                    1 if mention.get("is_primary_brand") else 0,
                ),
            )

        # 写入引用来源
        for citation in result.get("citations", []):
            await db.execute(
                """INSERT INTO citation_sources
                   (id, query_result_id, source_url, source_domain, source_type, source_title, citation_rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    result["id"],
                    citation.get("url"),
                    citation.get("domain"),
                    citation.get("type"),
                    citation.get("title"),
                    citation.get("rank", 0),
                ),
            )

    def _fallback_scenarios(self, brand_name: str) -> List[dict]:
        """兜底场景：当 AI 分析失败时的通用场景"""
        return [
            {"question": f"有哪些比较靠谱的品牌或公司推荐？", "category": "通用推荐"},
            {"question": f"行业内比较好的选择有哪些？各自有什么优势？", "category": "通用对比"},
            {"question": f"想找这方面的服务，应该怎么选？", "category": "通用选购"},
            {"question": f"这个行业的头部企业有哪些？", "category": "通用行业"},
            {"question": f"国内有哪些做得比较好的公司推荐？", "category": "通用地域"},
        ]
