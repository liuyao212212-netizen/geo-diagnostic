"""
HTML 报告生成引擎（V2 - 企业级可交付版）
- 附原始 AI 回复
- 交叉验证结果
- 数据来源说明
- 无 AI 免责声明
- 专业排版
"""
from typing import Dict, Any, List
from datetime import datetime
import json
from pathlib import Path
from string import Template


# 品牌颜色映射
BRAND_COLORS = {
    "美的": "#00a0e9",
    "海尔": "#e60012",
    "松下": "#003399",
    "西门子": "#009999",
    "格力": "#e63946",
    "方太": "#1a5276",
    "老板": "#c0392b",
    "TCL": "#2ecc71",
    "华凌": "#8e44ad",
    "小米": "#ff6700",
}

DEFAULT_COLOR = "#7f8c8d"


def get_brand_color(brand_name: str) -> str:
    for key, color in BRAND_COLORS.items():
        if key in brand_name:
            return color
    return DEFAULT_COLOR


class ReportGenerator:
    """HTML 报告生成器 V2"""

    def __init__(self):
        self.template_path = Path(__file__).parent / "report_template.html"

    def generate_html(
        self,
        brand_name: str,
        analysis: Dict[str, Any],
        task: Dict[str, Any],
        results: List[Dict[str, Any]],
        discovered_competitors: List[str] = None,
    ) -> str:
        """生成完整的 HTML 诊断报告"""
        brand_scores = analysis.get("brand_scores", [])
        heatmap = analysis.get("heatmap", {})
        sentiment = analysis.get("sentiment_summary", {})
        citations = analysis.get("citation_summary", {})
        cross_validation = analysis.get("cross_validation", {})
        raw_responses = analysis.get("raw_responses", [])

        primary_score = next(
            (s for s in brand_scores if s["brand_name"] == brand_name), None
        )

        platforms = heatmap.get("platforms", [])
        scenarios = heatmap.get("scenarios", [])
        competitors = task.get("competitors", [])

        # JSON 数据
        brand_names_json = json.dumps(
            [s["brand_name"] for s in brand_scores[:10]],
            ensure_ascii=False,
        )
        brand_values_json = json.dumps(
            [s["geo_score"] for s in brand_scores[:10]],
            ensure_ascii=False,
        )
        heatmap_formatted = self._format_heatmap_data(heatmap)
        sentiment_pie_json = json.dumps(
            [
                {"name": "正面", "value": sentiment.get("positive", 0)},
                {"name": "中性", "value": sentiment.get("neutral", 0)},
                {"name": "负面", "value": sentiment.get("negative", 0)},
            ],
            ensure_ascii=False,
        )

        # 表格行
        brand_table_rows = self._render_brand_table_rows(brand_scores, brand_name)
        sentiment_table_rows = self._render_sentiment_table_rows(sentiment.get("by_brand", []))
        cross_validation_rows = self._render_cross_validation_rows(
            cross_validation.get("items", [])
        )
        citation_section = self._render_citation_section(citations)
        raw_response_cards = self._render_raw_response_cards(raw_responses)

        chart_height = max(400, len(platforms) * 60 + len(scenarios) * 40)

        report_date = datetime.now().strftime("%Y年%m月%d日")
        primary_geo = primary_score["geo_score"] if primary_score else 0
        primary_rate = primary_score["mention_rate"] if primary_score else 0
        primary_rank = primary_score["avg_rank"] if primary_score else "-"
        primary_pos = primary_score["positive_rate"] if primary_score else 0

        cv_summary = cross_validation.get("summary", {})

        # 平台列表文本
        platform_list = "、".join(platforms)

        # 发现竞品信息
        if discovered_competitors is None:
            discovered_competitors = []
        user_competitors = task.get("competitors", [])
        user_comp_str = "、".join(user_competitors) if user_competitors else "无"
        discovered_comp_str = "、".join(discovered_competitors) if discovered_competitors else "无"
        # 发现竞品说明文案
        if discovered_competitors:
            discovery_note = f"系统通过 AI 平台自动发现了 {len(discovered_competitors)} 个竞品品牌：{discovered_comp_str}"
        else:
            discovery_note = "系统未能自动发现额外的竞品品牌（可能品牌知名度较低或领域较窄）"

        # 读取模板并用 string.Template 渲染（$var 语法，不与 CSS/JS 冲突）
        template_text = self.template_path.read_text(encoding="utf-8")
        template = Template(template_text)

        html = template.substitute(
            brand_name=brand_name,
            report_date=report_date,
            num_platforms=len(platforms),
            num_scenarios=len(scenarios),
            num_competitors=len(competitors),
            platform_list=platform_list,
            primary_geo=primary_geo,
            primary_rate=primary_rate,
            primary_rank=primary_rank,
            primary_pos=primary_pos,
            brand_names_json=brand_names_json,
            brand_values_json=brand_values_json,
            heatmap_formatted=heatmap_formatted,
            sentiment_pie_json=sentiment_pie_json,
            chart_height=chart_height,
            brand_table_rows=brand_table_rows,
            sentiment_table_rows=sentiment_table_rows,
            cross_validation_rows=cross_validation_rows,
            citation_section=citation_section,
            raw_response_cards=raw_response_cards,
            scenario_json=json.dumps(scenarios, ensure_ascii=False),
            platform_json=json.dumps(platforms, ensure_ascii=False),
            cv_high=cv_summary.get("high", 0),
            cv_medium=cv_summary.get("medium", 0),
            cv_low=cv_summary.get("low", 0),
            user_comp_str=user_comp_str,
            discovered_comp_str=discovered_comp_str,
            discovery_note=discovery_note,
            num_discovered=len(discovered_competitors),
        )
        return html

    def _render_brand_table_rows(self, brand_scores, brand_name) -> str:
        rows = []
        for i, s in enumerate(brand_scores):
            rank_class = f"rank-{i+1}" if i < 3 else ""
            is_primary = s["brand_name"] == brand_name
            style = ' style="font-weight:700;color:#0a0a23;"' if is_primary else ""
            sentiment_cls = (
                "sentiment-positive" if s["positive_rate"] >= 60
                else "sentiment-neutral" if s["positive_rate"] >= 30
                else "sentiment-negative"
            )
            platform_coverage = s.get("platform_coverage", "-")
            rows.append(
                f"<tr{style}>"
                f"<td><span class=\"rank-badge {rank_class}\">#{i+1}</span></td>"
                f"<td>{s['brand_name']}</td>"
                f"<td><strong>{s['geo_score']}</strong></td>"
                f"<td>{s['mention_rate']}%</td>"
                f"<td>{platform_coverage}%</td>"
                f"<td>#{s['avg_rank']}</td>"
                f"<td class=\"{sentiment_cls}\">{s['positive_rate']}%</td>"
                f"</tr>"
            )
        return "\n".join(rows)

    def _render_sentiment_table_rows(self, brand_sentiments) -> str:
        rows = []
        for s in brand_sentiments[:10]:
            rows.append(
                f"<tr>"
                f"<td>{s['brand_name']}</td>"
                f"<td class=\"sentiment-positive\">{s['positive']}</td>"
                f"<td class=\"sentiment-neutral\">{s['neutral']}</td>"
                f"<td class=\"sentiment-negative\">{s['negative']}</td>"
                f"<td>{s['positive_rate']}%</td>"
                f"</tr>"
            )
        return "\n".join(rows)

    def _render_cross_validation_rows(self, cv_items) -> str:
        rows = []
        for item in cv_items:
            confidence = item["confidence"]
            platforms_str = "、".join(item["mentioned_by"])

            # 排名对比
            ranks = item.get("ranks", {})
            if ranks:
                ranks_str = "、".join(f"{p}:#{r}" for p, r in ranks.items())
            else:
                ranks_str = "-"

            # 情感对比
            sentiments = item.get("sentiments", {})
            sentiment_map = {"positive": "正面", "neutral": "中性", "negative": "负面"}
            if sentiments:
                s_str = "、".join(f"{p}:{sentiment_map.get(s, s)}" for p, s in sentiments.items())
            else:
                s_str = "-"

            rows.append(
                f"<tr>"
                f"<td>{item['scenario']}</td>"
                f"<td>{item['brand_name']}</td>"
                f"<td>{platforms_str}</td>"
                f"<td><span class=\"confidence-badge {confidence}\">{item['confidence_label']}</span></td>"
                f"<td>{ranks_str}</td>"
                f"<td>{s_str}</td>"
                f"</tr>"
            )
        return "\n".join(rows)

    def _render_citation_section(self, citations) -> Dict:
        """渲染引用源部分（如果有引用）"""
        if not citations or citations.get("total", 0) == 0:
            return ""

        by_domain = citations.get("by_domain", [])
        domain_rows = []
        for d in by_domain[:10]:
            domain_rows.append(f"<tr><td>{d['domain']}</td><td>{d['count']}</td></tr>")

        html = (
            '<div class="section">\n'
            '<h2>五、引用源分析</h2>\n'
            '<div class="flex-row">\n'
            '<div>\n'
            '<h3>高频引用域名 TOP10</h3>\n'
            '<table class="brand-table">\n'
            '<thead><tr><th>域名</th><th>引用次数</th></tr></thead>\n'
            '<tbody>' + "\n".join(domain_rows) + '</tbody>\n'
            '</table>\n'
            '</div>\n'
            '</div>\n'
            '</div>'
        )
        return html

    def _render_raw_response_cards(self, raw_responses) -> str:
        """渲染原始 AI 回复卡片"""
        if not raw_responses:
            return "<p style=\"color:#999;\">暂无原始回复数据</p>"

        cards = []
        for r in raw_responses:
            platform = r["platform_name"]
            scenario = r["scenario_category"]
            question = r["scenario_question"]
            text = r["ai_response_text"] or ""
            duration = r.get("query_duration_ms", 0)
            queried_at = r.get("queried_at", "")

            # 清理 HTML 特殊字符
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            card = (
                '<div class="response-card">\n'
                '<div class="header">\n'
                f'<span class="platform">{platform}</span>\n'
                f'<span>场景：{scenario}</span>\n'
                f'<span>耗时：{duration}ms</span>\n'
                f'<span>{queried_at[:10] if queried_at else ""}</span>\n'
                '</div>\n'
                '<div class="question" style="margin-bottom:8px;font-weight:600;color:#333;">\n'
                f'问：{question}\n'
                '</div>\n'
                f'<div class="content">{text}</div>\n'
                '</div>'
            )
            cards.append(card)

        return "\n".join(cards)

    def _format_heatmap_data(self, heatmap: Dict) -> str:
        platforms = heatmap.get("platforms", [])
        data = heatmap.get("data", [])
        formatted = []
        for pi, row in enumerate(data):
            for si, val in enumerate(row):
                formatted.append(
                    f"[{pi}, {si}, {json.dumps(val) if val is not None else 'null'}]"
                )
        return f"[{', '.join(formatted)}]"
