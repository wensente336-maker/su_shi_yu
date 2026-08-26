from __future__ import annotations

import json
from typing import Any

from app.core.config import settings


def build_analysis_prompt(structured_data: dict[str, Any], report_content: str) -> str:
    return f"""你是企业经营分析助手。请严格依据以下事实数据和周报上下文，输出：
1. 本周核心经营结论；2. 数据变化的可能原因（必须标注为事实或推断）；3. 风险与待核实事项；4. 下周建议行动。
不得编造未提供的指标、客户事实或因果关系；不确定时明确说明信息不足。

## 结构化经营数据
{json.dumps(structured_data, ensure_ascii=False, indent=2)}

## 周报上下文（只读快照）
{report_content}
"""


def generate_analysis(prompt: str) -> tuple[str, str | None, str | None]:
    if settings.ai_provider != "openai" or not settings.openai_api_key:
        return "pending_model_configuration", None, "未配置可用的 AI 服务；已保存结构化数据、周报快照与分析提示词，配置 AI_PROVIDER=openai 和 OPENAI_API_KEY 后可重新生成。"
    from openai import OpenAI
    response = OpenAI(api_key=settings.openai_api_key).chat.completions.create(model=settings.ai_model, messages=[{"role": "system", "content": "你是谨慎、可审计的企业经营分析助手。"}, {"role": "user", "content": prompt}], temperature=0.2)
    return "generated", settings.ai_model, response.choices[0].message.content or "模型未返回内容"
