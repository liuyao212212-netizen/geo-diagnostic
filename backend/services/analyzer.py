"""
分析计算引擎（V2 - 企业级准确版）
- 提及率、平均排名、GEO品牌得分
- 情感分布分析
- 引用源分析
- 多平台交叉验证 + 可信度标注
- 原始回复保留
"""
from typing import List, Dict, Any
from collections import defaultdict


class Analyzer:
    """多维分析引擎 V2"""

    def __init__(
        self,
        brand_name: str,
        brand_aliases: List[str],
        competitors: List[str],
        all_brands: List[str],
    ):
        self.brand_name = brand_name
        self.brand_aliases = brand_aliases
        self.competitors = competitors
        self.all_brands = all_brands

    def analyze(
        self,
        results: List[Dict],
        mentions_by_result: Dict[str, List[Dict]],
        citations_by_result: Dict[str, List[Dict]],
    ) -> Dict:
        """
        执行完整的多维分析
        返回: 分析结果字典
        """
        # 构建查询结果映射
        results_map = {r["id"]: r for r in results}

        # 获取所有平台和场景列表
        platforms = list(set(r["platform_name"] for r in results))
        scenarios = list(set(r["scenario_category"] for r in results))

        # 1. 品牌得分分析
        brand_scores = self._calculate_brand_scores(
            results, mentions_by_result, platforms
        )

        # 2. 平台维度分析
        platform_analysis = self._calculate_platform_analysis(
            results, mentions_by_result, platforms
        )

        # 3. 场景×平台 热力图（主品牌提及排名得分）
        heatmap = self._generate_heatmap(
            results, mentions_by_result, platforms, scenarios
        )

        # 4. 情感分析
        sentiment_summary = self._calculate_sentiment(mentions_by_result)

        # 5. 引用源分析
        citation_summary = self._calculate_citations(citations_by_result)

        # 6. 多平台交叉验证
        cross_validation = self._cross_validate(
            results, mentions_by_result, platforms, scenarios
        )

        # 7. 各平台原始回复摘要
        raw_responses = self._collect_raw_responses(results)

        return {
            "brand_name": self.brand_name,
            "brand_scores": brand_scores,
            "platform_analysis": platform_analysis,
            "heatmap": heatmap,
            "sentiment_summary": sentiment_summary,
            "citation_summary": citation_summary,
            "cross_validation": cross_validation,
            "raw_responses": raw_responses,
        }

    def _calculate_brand_scores(
        self,
        results: List[Dict],
        mentions_by_result: Dict[str, List[Dict]],
        platforms: List[str],
    ) -> List[Dict]:
        """计算各品牌的综合得分"""
        scores = []
        total_queries = len(results)
        num_platforms = len(set(r["platform_name"] for r in results))
        results_map = {r["id"]: r for r in results}

        for brand in self.all_brands:
            mentions_data = []
            for rid, mentions in mentions_by_result.items():
                brand_mentions = [m for m in mentions if m["brand_name"] == brand]
                if brand_mentions:
                    mentions_data.extend(brand_mentions)

            # 提及率
            queries_with_mention = len(set(
                rid for rid, ms in mentions_by_result.items()
                if any(m["brand_name"] == brand for m in ms)
            ))
            mention_rate = queries_with_mention / total_queries if total_queries > 0 else 0

            # 平台覆盖率（被多少个不同平台提及）
            platforms_mentioned = len(set(
                results_map[rid]["platform_name"]
                for rid in mentions_by_result
                if any(m["brand_name"] == brand for m in mentions_by_result[rid])
                and rid in results_map
            ))
            platform_coverage = platforms_mentioned / num_platforms if num_platforms > 0 else 0

            # 平均排名（首次提及）
            first_ranks = []
            for rid, mentions in mentions_by_result.items():
                brand_ms = [m for m in mentions if m["brand_name"] == brand]
                if brand_ms:
                    first_ranks.append(brand_ms[0]["mention_rank"])
            avg_rank = sum(first_ranks) / len(first_ranks) if first_ranks else 99

            # 正面情感率
            positive_count = sum(1 for m in mentions_data if m["sentiment"] == "positive")
            positive_rate = positive_count / len(mentions_data) if mentions_data else 0

            # GEO 综合得分 V2: 提及率 × 排名加权 × 情感加权 × 平台覆盖加权
            rank_score = max(0, 1 - (avg_rank - 1) / 10)
            platform_weight = 0.5 + platform_coverage * 0.5  # 跨平台覆盖加权
            geo_score = round(
                mention_rate * rank_score * (0.5 + positive_rate * 0.5) * platform_weight * 100,
                1,
            )

            scores.append({
                "brand_name": brand,
                "mention_rate": round(mention_rate * 100, 1),
                "platform_coverage": round(platform_coverage * 100, 1),
                "avg_rank": round(avg_rank, 2),
                "positive_rate": round(positive_rate * 100, 1),
                "geo_score": geo_score,
                "total_mentions": len(mentions_data),
            })

        # 按得分降序
        scores.sort(key=lambda x: x["geo_score"], reverse=True)
        return scores

    def _calculate_platform_analysis(
        self,
        results: List[Dict],
        mentions_by_result: Dict[str, List[Dict]],
        platforms: List[str],
    ) -> List[Dict]:
        """按平台维度计算品牌表现"""
        platform_data = []

        for platform in platforms:
            platform_results = [r for r in results if r["platform_name"] == platform]
            platform_mentions = {
                rid: ms for rid, ms in mentions_by_result.items()
                if any(r["id"] == rid and r["platform_name"] == platform for r in results)
            }

            brand_scores = []
            for brand in self.all_brands:
                brand_mentions = []
                for rid, ms in platform_mentions.items():
                    brand_ms = [m for m in ms if m["brand_name"] == brand]
                    brand_mentions.extend(brand_ms)

                queries_with_mention = len(set(
                    rid for rid, ms in platform_mentions.items()
                    if any(m["brand_name"] == brand for m in ms)
                ))
                mention_rate = queries_with_mention / len(platform_results) if platform_results else 0

                first_ranks = []
                for rid, ms in platform_mentions.items():
                    for m in ms:
                        if m["brand_name"] == brand and m["mention_rank"] == 1:
                            first_ranks.append(1)
                        elif m["brand_name"] == brand:
                            first_ranks.append(m["mention_rank"])
                avg_rank = sum(first_ranks) / len(first_ranks) if first_ranks else 99

                brand_scores.append({
                    "brand_name": brand,
                    "mention_rate": round(mention_rate * 100, 1),
                    "avg_rank": round(avg_rank, 2),
                    "total_mentions": len(brand_mentions),
                })

            brand_scores.sort(key=lambda x: x["mention_rate"], reverse=True)
            platform_data.append({
                "platform_name": platform,
                "total_queries": len(platform_results),
                "brand_scores": brand_scores,
            })

        return platform_data

    def _generate_heatmap(
        self,
        results: List[Dict],
        mentions_by_result: Dict[str, List[Dict]],
        platforms: List[str],
        scenarios: List[str],
    ) -> Dict:
        """生成场景×平台的热力图数据"""
        data = []

        for platform in platforms:
            row = []
            for scenario in scenarios:
                matching = [
                    r for r in results
                    if r["platform_name"] == platform and r["scenario_category"] == scenario
                ]
                if matching:
                    r = matching[0]
                    ms = mentions_by_result.get(r["id"], [])
                    primary = [m for m in ms if m["brand_name"] == self.brand_name]
                    if primary:
                        rank = primary[0]["mention_rank"]
                        sentiment = primary[0]["sentiment"]
                        rank_score = max(0, 100 - (rank - 1) * 20)
                        sentiment_bonus = 10 if sentiment == "positive" else (-10 if sentiment == "negative" else 0)
                        row.append(round(rank_score + sentiment_bonus, 1))
                    else:
                        row.append(0)
                else:
                    row.append(None)
            data.append(row)

        return {
            "platforms": platforms,
            "scenarios": scenarios,
            "data": data,
        }

    def _calculate_sentiment(
        self, mentions_by_result: Dict[str, List[Dict]]
    ) -> Dict:
        """计算情感分析汇总"""
        all_mentions = []
        for ms in mentions_by_result.values():
            all_mentions.extend(ms)

        total = len(all_mentions)
        if total == 0:
            return {"total": 0, "positive": 0, "neutral": 0, "negative": 0}

        by_brand = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})
        for m in all_mentions:
            by_brand[m["brand_name"]][m["sentiment"]] += 1

        brand_sentiments = []
        for brand, counts in by_brand.items():
            brand_total = sum(counts.values())
            brand_sentiments.append({
                "brand_name": brand,
                "positive": counts["positive"],
                "neutral": counts["neutral"],
                "negative": counts["negative"],
                "positive_rate": round(counts["positive"] / brand_total * 100, 1),
                "total": brand_total,
            })

        brand_sentiments.sort(key=lambda x: x["positive_rate"], reverse=True)

        return {
            "total": total,
            "positive": sum(1 for m in all_mentions if m["sentiment"] == "positive"),
            "neutral": sum(1 for m in all_mentions if m["sentiment"] == "neutral"),
            "negative": sum(1 for m in all_mentions if m["sentiment"] == "negative"),
            "by_brand": brand_sentiments,
        }

    def _calculate_citations(
        self, citations_by_result: Dict[str, List[Dict]]
    ) -> Dict:
        """计算引用源分析"""
        all_citations = []
        for cs in citations_by_result.values():
            all_citations.extend(cs)

        if not all_citations:
            return {"total": 0, "by_type": [], "by_domain": []}

        by_type = defaultdict(int)
        for c in all_citations:
            by_type[c.get("type", "unknown")] += 1

        by_domain = defaultdict(int)
        for c in all_citations:
            by_domain[c.get("domain", "unknown")] += 1

        return {
            "total": len(all_citations),
            "by_type": [
                {"type": t, "count": c}
                for t, c in sorted(by_type.items(), key=lambda x: x[1], reverse=True)
            ],
            "by_domain": [
                {"domain": d, "count": c}
                for d, c in sorted(by_domain.items(), key=lambda x: x[1], reverse=True)[:20]
            ],
        }

    def _cross_validate(
        self,
        results: List[Dict],
        mentions_by_result: Dict[str, List[Dict]],
        platforms: List[str],
        scenarios: List[str],
    ) -> Dict:
        """
        多平台交叉验证：对比不同平台对同一场景的回复
        标注可信度：高可信（多平台一致）、中可信（单平台）、低可信（平台间矛盾）
        """
        validation_results = []

        # 按场景分组
        for scenario in scenarios:
            scenario_results = [
                r for r in results if r["scenario_category"] == scenario
            ]

            for brand in self.all_brands:
                platform_mentions = {}
                for r in scenario_results:
                    ms = mentions_by_result.get(r["id"], [])
                    brand_ms = [m for m in ms if m["brand_name"] == brand]
                    if brand_ms:
                        platform_mentions[r["platform_name"]] = brand_ms[0]

                if not platform_mentions:
                    continue

                num_platforms_mentioned = len(platform_mentions)
                platforms_list = list(platform_mentions.keys())

                # 判断可信度
                if num_platforms_mentioned >= 2:
                    # 多平台验证：检查排名和情感是否一致
                    ranks = [m["mention_rank"] for m in platform_mentions.values()]
                    sentiments = [m["sentiment"] for m in platform_mentions.values()]

                    rank_consistent = max(ranks) - min(ranks) <= 1
                    sentiment_consistent = len(set(sentiments)) == 1

                    if rank_consistent and sentiment_consistent:
                        confidence = "high"
                        confidence_label = "高可信（多平台一致）"
                    elif rank_consistent or sentiment_consistent:
                        confidence = "medium"
                        confidence_label = "中可信（部分一致）"
                    else:
                        confidence = "low"
                        confidence_label = "需核实（平台间差异）"
                else:
                    confidence = "medium"
                    confidence_label = "中可信（仅单平台验证）"

                validation_results.append({
                    "scenario": scenario,
                    "brand_name": brand,
                    "mentioned_by": platforms_list,
                    "num_platforms": num_platforms_mentioned,
                    "confidence": confidence,
                    "confidence_label": confidence_label,
                    "ranks": {
                        p: platform_mentions[p]["mention_rank"]
                        for p in platforms_list
                    },
                    "sentiments": {
                        p: platform_mentions[p]["sentiment"]
                        for p in platforms_list
                    },
                })

        # 统计可信度分布
        confidence_summary = {"high": 0, "medium": 0, "low": 0}
        for v in validation_results:
            confidence_summary[v["confidence"]] += 1

        return {
            "items": validation_results,
            "summary": confidence_summary,
            "total_platforms": len(platforms),
        }

    def _collect_raw_responses(self, results: List[Dict]) -> List[Dict]:
        """收集各平台原始回复"""
        raw = []
        for r in results:
            if r.get("ai_response_text"):
                raw.append({
                    "platform_name": r["platform_name"],
                    "scenario_category": r["scenario_category"],
                    "scenario_question": r["scenario_question"],
                    "ai_response_text": r["ai_response_text"],
                    "query_duration_ms": r.get("query_duration_ms"),
                    "queried_at": r.get("queried_at", ""),
                })
        return raw
