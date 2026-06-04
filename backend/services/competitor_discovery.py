"""
竞品自动发现服务 V5
直接让 LLM 返回结构化竞品 JSON，不再从回复中 NLP 提取。
逻辑：品牌名 + 行业常识 → LLM 直接输出 3-5 个竞品
"""
import re
from typing import List


class CompetitorDiscovery:
    """
    竞品自动发现引擎 V5
    直接让 LLM 返回 JSON 竞品列表，零噪音
    """

    def __init__(self, brand_name: str, brand_aliases: List[str] = None):
        self.brand_name = brand_name
        self.brand_aliases = brand_aliases or []

    def generate_discovery_query(self) -> str:
        """
        生成竞品发现查询 prompt
        LLM 直接返回 JSON，不需要从回复中提取
        """
        aliases_str = ""
        if self.brand_aliases:
            aliases_str = "（也叫" + "、".join(self.brand_aliases[:3]) + "）"

        prompt = (
            "你是行业分析专家。"
            "请分析" + self.brand_name + aliases_str + "所在的行业，"
            "列举这个行业里最主要的 3-5 个竞品品牌或公司。"
            "只返回 JSON，不要加任何解释文字。"
            "格式："
            '{"competitors": ["竞品1", "竞品2", "竞品3"]}'
        )
        return prompt

    @staticmethod
    def parse_discovery_response(response_text: str, brand_name: str = "") -> List[str]:
        """
        解析 LLM 返回的竞品 JSON
        输入：LLM 的回复文本 + 目标品牌名（用于过滤）
        输出：竞品名称列表（去重、过滤）
        """
        import json
        import re

        if not response_text:
            print("[CompetitorDiscovery] 空回复，无法解析竞品", flush=True)
            return []

        print("[CompetitorDiscovery] LLM原始回复前200字: " + response_text[:200], flush=True)

        # 策略1：提取被 ```json ... ``` 包裹的 JSON
        json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                competitors = data.get("competitors", [])
                result = CompetitorDiscovery._filter_competitors(competitors, brand_name)
                if result:
                    print("[CompetitorDiscovery] 从markdown代码块解析到竞品: " + str(result), flush=True)
                    return result
            except (json.JSONDecodeError, AttributeError):
                pass

        # 策略2：直接搜索 JSON 对象（可能混在文本中）
        json_match = re.search(r'\{[^{}]*"competitors"\s*:\s*\[[^\]]*\][^{}]*\}', response_text)
        if not json_match:
            # 更宽松的匹配：允许嵌套
            json_match = re.search(r'\{[\s\S]*?"competitors"[\s\S]*?\}', response_text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                competitors = data.get("competitors", [])
                result = CompetitorDiscovery._filter_competitors(competitors, brand_name)
                if result:
                    print("[CompetitorDiscovery] 从文本中提取到竞品: " + str(result), flush=True)
                    return result
            except (json.JSONDecodeError, AttributeError):
                pass

        # 策略3：尝试直接解析整个文本
        try:
            data = json.loads(response_text.strip())
            competitors = data.get("competitors", [])
            result = CompetitorDiscovery._filter_competitors(competitors, brand_name)
            if result:
                print("[CompetitorDiscovery] 直接JSON解析到竞品: " + str(result), flush=True)
                return result
        except (json.JSONDecodeError, AttributeError):
            pass

        # 策略4：LLM 可能用了中文 key 或列表格式
        # 尝试匹配编号列表: 1. xxx 2. xxx
        list_match = re.findall(r'(?:\d+[\.\、\)]\s*)([^\n\d]{2,20}?)(?=\d+[\.\、\)]|$|\n)', response_text)
        if list_match:
            result = CompetitorDiscovery._filter_competitors(list_match, brand_name)
            if result:
                print("[CompetitorDiscovery] 从编号列表提取到竞品: " + str(result), flush=True)
                return result

        print("[CompetitorDiscovery] 所有解析策略均未匹配到竞品", flush=True)
        return []

    @staticmethod
    def _filter_competitors(raw_list: List[str], brand_name: str) -> List[str]:
        """
        过滤竞品列表：
        1. 去掉空字符串和超短词（<2字符）
        2. 去掉目标品牌本身
        3. 去掉纯数字、纯标点
        4. 去重
        5. 最多保留 8 个
        """
        if not raw_list:
            return []

        filtered = []
        seen = set()

        for comp in raw_list:
            if not comp or not isinstance(comp, str):
                continue
            comp = comp.strip()
            if not comp or len(comp) < 2:
                continue
            # 去掉序号前缀
            comp = re.sub(r'^[\d\.\、\)\s]+', '', comp).strip()
            if len(comp) < 2:
                continue
            # 去掉引号
            comp = comp.strip('"\'""''')
            # 跳过纯数字
            if comp.isdigit():
                continue
            # 跳过目标品牌
            if brand_name and (comp == brand_name or comp in brand_name or brand_name in comp):
                continue
            # 去重
            if comp not in seen:
                seen.add(comp)
                filtered.append(comp)

        return filtered[:8]
