"""
关键词自动生成引擎 V5
基于品牌名 + 行业 + 竞品，LLM 生成 15-20 个消费者真实搜索关键词。
覆盖4个维度：品类词、对比词、场景词、评测词。
"""
from typing import List, Dict, Any


class KeywordGenerator:
    """
    关键词自动生成引擎
    基于品牌名 + 行业 + 竞品，LLM 生成多维度搜索关键词
    """

    # 关键词维度模板
    KEYWORD_DIMENSIONS = [
        {
            "type": "category",
            "label": "品类词",
            "description": "用户搜索某类产品/服务时的直接提问",
            "example": "什么空调好、高端冰箱推荐",
        },
        {
            "type": "comparison",
            "label": "对比词",
            "description": "用户对比多个品牌时的提问",
            "example": "美的vs格力、海尔和卡萨帝哪个好",
        },
        {
            "type": "scenario",
            "label": "场景词",
            "description": "用户在特定场景下的问题",
            "example": "租房买什么洗衣机、新房装修买什么冰箱",
        },
        {
            "type": "review",
            "label": "评测词",
            "description": "用户想了解产品评价时的提问",
            "example": "美的冰箱怎么样、海尔售后好吗",
        },
    ]

    def __init__(
        self, brand_name: str, industry: str = "", competitors: List[str] = None
    ):
        self.brand_name = brand_name
        self.industry = industry or "相关领域"
        self.competitors = competitors or []

    def generate_keyword_query(self) -> str:
        """
        生成关键词生成查询 prompt
        LLM 直接返回 JSON，不需要从回复中提取
        """
        comp_str = ""
        if self.competitors:
            comp_str = "，主要竞品包括" + "、".join(self.competitors[:5])

        prompt = (
            "你是消费者搜索行为分析专家。"
            "请分析" + self.brand_name + "所在的" + self.industry + "领域" + comp_str + "，"
            "生成 15-20 个消费者在 AI 平台或搜索引擎中真实会搜索的提问词。"
            "关键词要覆盖以下4个维度："
            "1) 品类词（直接问产品/服务类型）"
            "2) 对比词（对比多个品牌）"
            "3) 场景词（特定使用场景）"
            "4) 评测词（了解产品评价）"
            "只返回 JSON，不要加任何解释文字。"
            "格式："
            '{"keywords": ["关键词1", "关键词2", ..., "关键词15-20"]}'
        )
        return prompt

    @staticmethod
    def parse_keyword_response(response_text: str) -> List[Dict[str, str]]:
        """
        解析 LLM 返回的关键词 JSON
        输入：LLM 的回复文本
        输出：关键词列表（带维度标签）
        """
        import json
        import re

        # 尝试从回复中提取 JSON（可能被 ```json ``` 包裹）
        json_match = re.search(r'\{[\s\S]*"keywords"[\s\S]*\}', response_text)
        if not json_match:
            # 尝试直接解析整个文本
            try:
                data = json.loads(response_text.strip())
                keywords = data.get("keywords", [])
                return KeywordGenerator._tag_keywords(keywords)
            except (json.JSONDecodeError, AttributeError):
                return []

        try:
            data = json.loads(json_match.group())
            keywords = data.get("keywords", [])
            return KeywordGenerator._tag_keywords(keywords)
        except (json.JSONDecodeError, AttributeError):
            return []

    @staticmethod
    def _tag_keywords(keywords: List[str]) -> List[Dict[str, str]]:
        """
        为关键词打维度标签
        根据关键词内容判断属于哪个维度
        """
        if not keywords:
            return []

        tagged = []
        seen = set()

        for kw in keywords:
            if not kw or not isinstance(kw, str):
                continue
            kw = kw.strip()
            if not kw or kw in seen:
                continue

            seen.add(kw)

            # 判断维度
            dimension = KeywordGenerator._classify_keyword(kw)
            tagged.append({"keyword": kw, "dimension": dimension})

        return tagged[:20]  # 最多20个

    @staticmethod
    def _classify_keyword(keyword: str) -> str:
        """
        判断关键词属于哪个维度
        基于关键词内容和句式特征
        """
        kw_lower = keyword.lower()

        # 对比词：包含"vs"、"和"、"还是"、"哪个好"等
        if any(
            sep in kw_lower
            for sep in ["vs", "和", "与", "还是", "哪个好", "对比"]
        ):
            return "comparison"

        # 评测词：包含"怎么样"、"好不好"、"评测"、"体验"等
        if any(
            word in kw_lower
            for word in ["怎么样", "好不好", "评测", "体验", "值得买", "缺点"]
        ):
            return "review"

        # 场景词：包含"租房"、"新房"、"装修"、"办公室"等场景词
        if any(
            word in kw_lower
            for word in ["租房", "新房", "装修", "办公室", "卧室", "客厅", "厨房"]
        ):
            return "scenario"

        # 默认归类为品类词
        return "category"
