"""
AI 回答结果解析引擎（V2 - 企业级准确版）
- 品牌名称提取：jieba 分词 + 自定义品牌词典 + 边界匹配
- 情感分析：扩展词典 + 滑动窗口 + 强否定词处理
- 排名提取：按文本出现顺序
- 引用源提取
"""
import re
import jieba
import jieba.posseg as pseg
from typing import List, Dict, Any, Tuple
from collections import OrderedDict


# ============ 引用源类型分类映射 ============

SOURCE_TYPE_MAP = {
    "官方": "official",
    "门户": "portal",
    "电商": "ecommerce",
    "社区": "community",
    "视频": "video",
    "媒体": "media",
    "评测": "review",
    "百科": "wiki",
}

DOMAIN_TYPE_MAP = {
    "jd.com": "ecommerce",
    "tmall.com": "ecommerce",
    "taobao.com": "ecommerce",
    "suning.com": "ecommerce",
    "pinduoduo.com": "ecommerce",
    "douyin.com": "video",
    "bilibili.com": "video",
    "youtube.com": "video",
    "baidu.com": "portal",
    "zhihu.com": "community",
    "weibo.com": "community",
    "smzdm.com": "review",
    "zol.com.cn": "review",
    "pconline.com.cn": "review",
    "baike.baidu.com": "wiki",
    "36kr.com": "media",
    "ifanr.com": "media",
    "sspai.com": "media",
    "ithome.com": "media",
}


# ============ 情感分析词典（V2 扩展版） ============

POSITIVE_WORDS = {
    # 品质类
    "好", "优秀", "出色", "卓越", "顶尖", "一流", "精品", "高品质", "优质",
    "可靠", "稳定", "耐用", "结实", "精致", "精湛", "匠心",
    # 推荐/认可类
    "推荐", "值得", "首选", "好评", "认可", "信赖", "放心", "满意", "点赞",
    "口碑好", "口碑不错", "深受好评", "广受好评", "深受用户喜爱", "用户好评",
    # 性价比类
    "性价比", "实惠", "划算", "超值", "物超所值", "经济实惠",
    # 功能类
    "智能", "省电", "节能", "静音", "环保", "创新", "领先", "先进",
    # 地位类
    "领先", "龙头", "领军", "头部", "标杆", "经典", "旗舰", "王者",
    "行业领先", "市场领先", "全球领先", "国内领先",
    # 外观/体验类
    "好看", "漂亮", "大气", "高端", "时尚", "设计精美", "简约大气",
    "舒适", "人性化", "体验好", "操作简单", "使用方便", "上手快",
    # 销售类
    "畅销", "热销", "爆款", "销量第一", "销量领先",
}

NEGATIVE_WORDS = {
    # 质量类
    "差", "不好", "质量差", "劣质", "粗糙", "廉价感",
    # 问题/故障类
    "问题", "故障", "维修", "投诉", "退货", "召回", "翻新",
    # 体验差类
    "噪音", "费电", "不稳定", "售后差", "不耐用", "难用",
    "不方便", "不推荐", "不靠谱", "不理想", "不满意",
    # 情感类
    "后悔", "失望", "踩坑", "翻车", "避雷", "劝退", "差评",
    "性价比低", "太贵", "昂贵", "溢价严重",
}

# 否定词（前缀修饰）
NEGATION_WORDS = {"不", "没", "没有", "无", "未", "别", "非", "缺", "少"}
# 强化词（修饰情感强度）
INTENSIFIERS = {"很", "非常", "特别", "极其", "十分", "相当", "比较", "略", "稍微"}


class ResponseParser:
    """AI 回答解析器 V3 - 支持开放品牌发现"""

    def __init__(
        self,
        brand_name: str,
        brand_aliases: List[str],
        competitors: List[str],
    ):
        self.brand_name = brand_name
        self.brand_aliases = brand_aliases
        self.competitors = competitors

        # 构建品牌匹配表（名称 → 规范名称）
        self.brand_match_map: Dict[str, str] = OrderedDict()
        self.brand_match_map[brand_name] = brand_name
        for alias in brand_aliases:
            if alias != brand_name:
                self.brand_match_map[alias] = brand_name
        for comp in competitors:
            self.brand_match_map[comp] = comp

        # 自动提取品牌简称（去掉常见后缀）— 仅用于 jieba 分词验证，不加到正则里避免误匹配
        self.short_name_map = self._build_short_name_variants()

        # 所有品牌词集合（用于分词后验证，含简称）
        self.all_brand_names = set(self.brand_match_map.keys()) | set(self.short_name_map.keys())

        # 编译正则：只用完整品牌名（不含简称），避免常见短词误匹配
        full_names_only = [n for n in self.brand_match_map.keys() if n not in self.short_name_map]
        sorted_names = sorted(full_names_only, key=len, reverse=True)
        pattern = "|".join(re.escape(n) for n in sorted_names)
        self.brand_regex = re.compile(pattern)

        # 初始化 jieba 自定义词典
        self._init_jieba_dictionary()

        # 动态发现的品牌（在 parse 过程中逐步积累）
        self.discovered_brands: Dict[str, str] = OrderedDict()

    # 常见公司/品牌后缀，去掉后得到简称
    _NAME_SUFFIXES = ["集团", "公司", "科技", "网络", "营销", "传媒", "数字", "信息",
                      "智能", "时代", "超人", "联众", "光标", "优品", "互联", "在线"]

    # 高频常见汉语词汇 — 不能作为品牌简称（避免误匹配）
    _COMMON_WORDS_BLACKLIST = {
        "增长", "发展", "提高", "增加", "减少", "降低", "提升", "下降",
        "公司", "企业", "集团", "网络", "科技", "信息", "服务", "产品",
        "用户", "客户", "市场", "行业", "平台", "系统", "工具", "软件",
        "设备", "品牌", "价格", "质量", "效果", "优势", "特点", "功能",
        "性能", "设计", "外观", "体验", "操作", "使用", "购买", "销售",
        "推荐", "选择", "比较", "分析", "评价", "评论", "口碑", "排名",
    }

    def _build_short_name_variants(self) -> Dict[str, str]:
        """为品牌名自动提取简称变体，支持AI回复中的简称提及
        返回独立的简称→规范名映射，仅用于jieba分词验证，不加入正则
        """
        short_map = {}
        for name, canonical in list(self.brand_match_map.items()):
            # 去掉常见后缀得到简称
            short = name
            for suffix in self._NAME_SUFFIXES:
                if short.endswith(suffix) and len(short) > len(suffix) + 1:
                    short = short[:-len(suffix)]
                    break
            # 简称至少2个字，且不能是高频常见词，避免误匹配
            if (short and short != name and len(short) >= 2
                    and short not in self.brand_match_map
                    and short not in self._COMMON_WORDS_BLACKLIST):
                short_map[short] = canonical
        return short_map

    def _init_jieba_dictionary(self):
        """将品牌词加入 jieba 词典，确保分词时品牌不被拆分"""
        for name in self.all_brand_names:
            # 设置高词频，确保品牌词优先被识别为整体
            jieba.add_word(name, freq=100000, tag="nz")

    def extract_brands(self, text: str) -> List[Tuple[str, int]]:
        """
        从文本中提取品牌名称及其出现位置
        使用 jieba 分词 + 正则双重验证，确保准确率
        返回: [(规范品牌名, 字符位置), ...]
        """
        found = []

        # 方法1：正则匹配（精确匹配品牌词）
        for match in self.brand_regex.finditer(text):
            raw_name = match.group()
            canonical = self.brand_match_map.get(raw_name, raw_name)
            found.append((canonical, match.start()))

        # 方法2：jieba 分词验证（捕获正则可能遗漏的变体，含简称）
        # 合并完整名和简称的映射表
        combined_map = {**self.brand_match_map, **self.short_name_map}
        words = list(jieba.cut(text))
        pos = 0
        for word in words:
            if word in combined_map:
                canonical = combined_map[word]
                # 检查是否已由正则捕获（避免重复）
                already_found = any(
                    abs(p - pos) < len(word) and c == canonical
                    for c, p in found
                )
                if not already_found:
                    found.append((canonical, pos))
            pos += len(word)

        # 按位置排序
        found.sort(key=lambda x: x[1])
        return found

    def analyze_sentiment(self, text: str, brand_name: str) -> str:
        """
        分析文本中对指定品牌的情感倾向
        V2: 滑动窗口 + 否定词处理 + 上下文加权
        返回: positive / neutral / negative
        """
        context = self._extract_brand_context(text, brand_name)
        if not context.strip():
            return "neutral"

        pos_score = 0
        neg_score = 0

        # 滑动窗口分析（窗口大小=上下文中的词数，步长=1）
        words = list(jieba.cut(context))
        window_size = 5  # 5个词的窗口

        for i in range(len(words)):
            window = words[i:i + window_size]
            for word in window:
                if word in POSITIVE_WORDS:
                    # 检查前置否定词
                    negated = self._check_negation(words, i)
                    if negated:
                        neg_score += 1
                    else:
                        # 检查强化词
                        intensified = self._check_intensifier(words, i)
                        pos_score += 2 if intensified else 1
                elif word in NEGATIVE_WORDS:
                    negated = self._check_negation(words, i)
                    if negated:
                        pos_score += 1
                    else:
                        intensified = self._check_intensifier(words, i)
                        neg_score += 2 if intensified else 1

        if pos_score > neg_score:
            return "positive"
        elif neg_score > pos_score:
            return "negative"
        return "neutral"

    def _check_negation(self, words: List[str], index: int) -> bool:
        """检查当前词前面是否有否定词"""
        for i in range(max(0, index - 3), index):
            if words[i] in NEGATION_WORDS:
                return True
        return False

    def _check_intensifier(self, words: List[str], index: int) -> bool:
        """检查当前词前面是否有强化词"""
        for i in range(max(0, index - 2), index):
            if words[i] in INTENSIFIERS:
                return True
        return False

    def _extract_brand_context(self, text: str, brand_name: str) -> str:
        """提取品牌相关的上下文段落（扩展到前后句）"""
        # 按句号、换行、分号分割
        sentences = re.split(r'[。\n；！？]', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # 找到包含品牌名的句子索引
        brand_indices = [i for i, s in enumerate(sentences) if brand_name in s]

        if not brand_indices:
            return text[:500]

        # 提取目标句 + 前后各一句（扩大上下文）
        contexts = []
        for idx in brand_indices:
            start = max(0, idx - 1)
            end = min(len(sentences), idx + 2)
            contexts.extend(sentences[start:end])

        return " ".join(contexts) if contexts else text[:500]

    def extract_citations(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取引用来源（URL）"""
        citations = []
        url_pattern = re.compile(r'https?://[^\s\]）)）}]{2,200}')

        for rank, match in enumerate(url_pattern.finditer(text), 1):
            url = match.group()
            domain = self._extract_domain(url)
            source_type = DOMAIN_TYPE_MAP.get(domain, self._guess_source_type(url))

            citations.append({
                "url": url,
                "domain": domain,
                "type": source_type,
                "title": "",
                "rank": rank,
            })

        return citations

    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        return match.group(1) if match else ""

    def _guess_source_type(self, url: str) -> str:
        """根据 URL 特征猜测来源类型"""
        if ".com.cn" in url or ".cn" in url:
            return "portal"
        if "review" in url or "test" in url or "pingce" in url:
            return "review"
        if "baike" in url:
            return "wiki"
        if "gov" in url:
            return "official"
        return "media"

    def discover_new_brands(self, text: str) -> List[Tuple[str, int]]:
        """
        开放品牌发现：从文本中提取不在预设列表中的公司/品牌名
        使用多种策略：
        1. competitor_discovery 的公司名提取（带后缀的B2B公司名）
        2. jieba 专有名词提取（消费品牌名如"格力"、"美的"）
        """
        from collections import Counter

        known_names = set(self.brand_match_map.keys()) | set(self.short_name_map.keys()) | set(self.discovered_brands.keys())
        candidates: Counter = Counter()

        # 策略1：从 competitor_discovery 提取（带公司后缀）
        try:
            from services.competitor_discovery import extract_companies_from_text
            discovered = extract_companies_from_text(
                text, self.brand_name, self.brand_aliases
            )
            for name in discovered:
                if name not in known_names:
                    candidates[name] += 2
        except Exception:
            pass

        # 策略2：严格模式提取品牌名
        # 匹配模式：
        # A) jieba标注为 nr/nz/nrt 的 2-4 字词（"美的"被标为nr）
        # B) jieba标注为 n 的 2-4 字词，但后接"的"+产品词 或 后接产品词
        # C) n标注词本身包含产品词（如"格力空调"→提取"格力"）
        words_list = [(str(w.word), w.flag) for w in pseg.cut(text)]
        _product_words = {"冰箱", "空调", "洗衣机", "电视", "手机", "电脑",
                          "烤箱", "热水器", "油烟机", "净化器", "路由器", "微波炉",
                          "产品", "品牌", "公司", "集团", "科技", "技术", "服务"}
        _noise_words = {"的", "了", "是", "在", "有", "和", "与", "但", "也",
                        "很", "非常", "特别", "比较", "一个", "不错", "一般",
                        "出色", "精良", "偏高", "不错", "智能", "做工", "表现",
                        "的话", "性价比", "方面", "国内", "国外",
                        "冰箱", "空调", "洗衣机", "电视", "手机", "电脑",
                        "市场", "领域", "行业"}

        for i, (word, flag) in enumerate(words_list):
            if not (2 <= len(word) <= 4):
                continue
            if word in known_names or word == self.brand_name:
                continue
            if word in self._COMMON_WORDS_BLACKLIST:
                continue

            # 模式A: jieba标注为人名/专有名词 → 大概率是品牌
            if flag in ("nz", "nrt", "nr"):
                candidates[word] += 2
                continue

            # n 标注的词需要更多验证
            if flag == "n":
                # 跳过纯产品/领域词
                if word in _noise_words:
                    continue
                # 模式C: 包含产品词（如"格力空调"）→提取品牌前缀
                has_product = False
                extracted = word
                for pw in _product_words:
                    if word.endswith(pw) and len(word) > len(pw):
                        extracted = word[:-len(pw)]
                        has_product = True
                        break
                if has_product and len(extracted) >= 2:
                    if extracted not in known_names and extracted != self.brand_name:
                        candidates[extracted] += 2
                    continue
                # 模式B: 后接 "的" 或产品词
                if i + 1 < len(words_list):
                    next_word = words_list[i + 1][0]
                    if next_word in ("的",) or next_word in _product_words:
                        candidates[word] += 1

        # 去重
        found = []
        for name, count in candidates.most_common(20):
            if name not in self.discovered_brands and name not in known_names:
                self.discovered_brands[name] = name
                idx = text.find(name)
                found.append((name, idx if idx >= 0 else 0))
                jieba.add_word(name, freq=100000, tag="nz")

        # 动态扩展正则
        if self.discovered_brands:
            all_full = [n for n in (list(self.brand_match_map.keys()) + list(self.discovered_brands.keys()))
                        if n not in self.short_name_map]
            sorted_all = sorted(set(all_full), key=len, reverse=True)
            if sorted_all:
                self.brand_regex = re.compile("|".join(re.escape(n) for n in sorted_all))

        return found

    def get_all_discovered_brands(self) -> List[str]:
        """获取所有动态发现的品牌名"""
        return list(self.discovered_brands.keys())

    def parse(self, response_text: str) -> Tuple[List[Dict], List[Dict]]:
        """
        完整解析 AI 回答
        V3: 先匹配预设品牌，再开放发现新品牌
        返回: (品牌提及列表, 引用来源列表)
        """
        if not response_text:
            return [], []

        # 1. 品牌提取 + 排名（jieba + 正则双重验证）
        brand_occurrences = self.extract_brands(response_text)

        # 2. 开放发现：提取预设列表之外的品牌
        new_brands = self.discover_new_brands(response_text)
        for brand_name, position in new_brands:
            brand_occurrences.append((brand_name, position))

        # 按位置排序
        brand_occurrences.sort(key=lambda x: x[1])

        # 去重，保留首次出现位置
        seen = set()
        mentions = []
        for brand_name, position in brand_occurrences:
            if brand_name not in seen:
                seen.add(brand_name)
                sentiment = self.analyze_sentiment(response_text, brand_name)
                context = self._extract_brand_context(response_text, brand_name)
                mentions.append({
                    "brand_name": brand_name,
                    "mention_rank": len(seen),
                    "sentiment": sentiment,
                    "mention_context": context[:300],
                    "is_primary_brand": brand_name == self.brand_name,
                    "is_discovered": brand_name in self.discovered_brands,  # V3: 标记是否为动态发现
                })

        # 3. 引用源提取
        citations = self.extract_citations(response_text)

        return mentions, citations
