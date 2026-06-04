"""
诊断场景自动发现服务
根据品牌名称和品牌别名，自动通过 AI 分析品牌所在行业，
生成多维度、贴近真实用户搜索习惯的诊断场景。
用户无需手动填写提问场景，系统自动生成。
"""
from typing import List, Dict, Optional


class ScenarioDiscovery:
    """
    场景自动发现引擎
    根据品牌名称，通过 AI 分析品牌所在行业，自动生成多维度诊断场景。
    """

    # 场景生成维度模板
    # 每个维度覆盖一类真实用户搜索意图
    SCENARIO_DIMENSIONS = [
        {
            "type": "recommendation",
            "label": "推荐类",
            "prompt_suffix": "请推荐一下{industry}领域比较靠谱的品牌/公司，有哪些选择？",
            "category_template": "{sub_category}推荐",
        },
        {
            "type": "comparison",
            "label": "对比类",
            "prompt_suffix": "{industry}领域哪个品牌/公司比较好？各自有什么优势和劣势？",
            "category_template": "{sub_category}对比",
        },
        {
            "type": "selection_guide",
            "label": "选购类",
            "prompt_suffix": "想找{industry}方面的服务/产品，应该怎么选择？有什么建议？",
            "category_template": "{sub_category}选购",
        },
        {
            "type": "knowledge",
            "label": "知识科普类",
            "prompt_suffix": "了解一下{industry}行业，头部企业有哪些？这个行业现状如何？",
            "category_template": "{sub_category}行业",
        },
        {
            "type": "region",
            "label": "地域类",
            "prompt_suffix": "在{region}有没有比较好的{industry}公司/品牌推荐？",
            "category_template": "地域-{sub_category}推荐",
        },
        {
            "type": "niche",
            "label": "细分需求类",
            "prompt_suffix": "需要{industry}方面{niche_service}的服务，哪家做得比较好？",
            "category_template": "{sub_category}细分",
        },
    ]

    def __init__(self, brand_name: str, brand_aliases: List[str] = None):
        self.brand_name = brand_name
        self.brand_aliases = brand_aliases or []

    def generate_brand_analysis_query(self) -> str:
        """
        生成品牌行业分析查询
        让 AI 分析品牌所在行业，返回结构化信息用于后续场景生成
        """
        aliases_str = ""
        if self.brand_aliases:
            aliases_str = "（也叫" + "、".join(self.brand_aliases[:3]) + "）"

        return (
            "请分析品牌"" + self.brand_name + """ + aliases_str + "的以下信息，"
            "请严格按照下面的 JSON 格式回答，不要加任何其他文字：\n\n"
            "{\n"
            '  "industry": "品牌所在的一级行业（如：数字营销、家电制造、SaaS软件、电商运营等），\n'
            '  "sub_categories": ["2-3个细分领域（如：SEO优化、SEM投放、社交媒体营销等）"],\n'
            '  "product_types": ["2-3个核心产品或服务类型（如：搜索引擎优化服务、品牌营销策划、数据分析平台等）"],\n'
            '  "target_clients": ["主要客户类型（如：中小企业、大型品牌、出海企业等）"],\n'
            '  "region": "主要服务区域或总部所在地（如：北京、中国、全球等），\n'
            '  "niche_services": ["2-3个细分服务或特色能力（如：AI营销、跨境电商运营、品牌出海等）"]\n'
            "}"
        )

    def parse_brand_analysis(self, analysis_text: str) -> Dict:
        """
        解析 AI 返回的品牌分析 JSON
        """
        import json
        import re

        # 提取 JSON 内容（可能被 markdown 代码块包裹）
        json_match = re.search(r'\{[\s\S]*\}', analysis_text)
        if not json_match:
            return self._fallback_analysis()

        try:
            result = json.loads(json_match.group())
            # 验证必要字段
            if not result.get("industry"):
                return self._fallback_analysis()
            return result
        except (json.JSONDecodeError, KeyError):
            return self._fallback_analysis()

    def generate_scenarios(self, analysis: Dict) -> List[Dict]:
        """
        根据品牌分析结果，生成多维度诊断场景

        返回: [{"question": "...", "category": "..."}, ...]
        """
        industry = analysis.get("industry", "相关领域")
        sub_categories = analysis.get("sub_categories", [industry])
        product_types = analysis.get("product_types", [])
        region = analysis.get("region", "国内")
        niche_services = analysis.get("niche_services", [])

        scenarios = []

        for dim in self.SCENARIO_DIMENSIONS:
            for sub_cat in sub_categories[:2]:  # 每个维度取最多2个细分领域
                question = self._build_question(dim, industry, sub_cat, region, niche_services)
                category = dim["category_template"].format(sub_category=sub_cat)

                # 避免重复
                if not any(s["question"] == question for s in scenarios):
                    scenarios.append({
                        "question": question,
                        "category": category,
                        "auto_generated": True,
                    })

                if len(scenarios) >= 8:
                    return scenarios

        # 补充：如果有产品类型信息，添加产品维度的场景
        for pt in product_types[:2]:
            question = f"想找{pt}方面的服务或产品，有哪些好的选择推荐？"
            category = f"{industry}-{pt[:4]}"
            if not any(s["question"] == question for s in scenarios):
                scenarios.append({
                    "question": question,
                    "category": category,
                    "auto_generated": True,
                })

        return scenarios[:8]

    def _build_question(
        self,
        dimension: Dict,
        industry: str,
        sub_category: str,
        region: str,
        niche_services: List[str],
    ) -> str:
        """根据维度模板构建具体问题"""
        suffix = dimension["prompt_suffix"]

        # 填充行业和细分领域
        question = suffix.format(
            industry=industry,
            sub_category=sub_category,
            region=region,
            niche_service=niche_services[0] if niche_services else sub_category,
        )

        return question

    def _fallback_analysis(self) -> Dict:
        """
        兜底分析：当 AI 返回无法解析时的默认值
        使用通用模板生成场景
        """
        return {
            "industry": "相关服务",
            "sub_categories": ["相关服务"],
            "product_types": [],
            "target_clients": [],
            "region": "国内",
            "niche_services": [],
        }
