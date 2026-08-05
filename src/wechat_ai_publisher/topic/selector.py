from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from wechat_ai_publisher.domain.models import SourceSignal

HIGH_VALUE_TERMS = {
    "productivity": 3,
    "workflow": 2,
    "automation": 2,
    "meeting": 2,
    "document": 1,
    "writing": 1,
    "email": 1,
    "spreadsheet": 1,
    "presentation": 1,
    "knowledge": 1,
    "learning": 2,
    "task": 1,
    "calendar": 1,
    "collaboration": 1,
    "privacy": 8,
    "risk": 7,
    "career": 9,
    "job": 8,
    "layoff": 10,
    "salary": 9,
    "side hustle": 8,
    "money": 9,
    "cost": 8,
    "saving": 8,
    "scam": 10,
    "fraud": 10,
    "health": 8,
    "education": 7,
    "family": 8,
    "children": 8,
    "travel": 7,
    "office": 1,
    "效率": 3,
    "工作流": 2,
    "自动化": 2,
    "会议": 2,
    "文档": 1,
    "写作": 1,
    "邮件": 1,
    "表格": 1,
    "学习": 2,
    "隐私": 8,
    "风险": 7,
    "避坑": 9,
    "工作": 8,
    "职场": 9,
    "失业": 10,
    "裁员": 10,
    "工资": 9,
    "降薪": 10,
    "副业": 8,
    "钱": 9,
    "省钱": 8,
    "消费": 8,
    "消费降级": 9,
    "诈骗": 10,
    "被骗": 10,
    "健康": 8,
    "看病": 9,
    "养老": 8,
    "老人": 8,
    "孩子": 8,
    "教育": 7,
    "家庭": 8,
    "情绪": 7,
    "旅行": 7,
    "agent": 2,
    "security": 3,
    "testing": 2,
    "observability": 1,
    "java": 1,
    "spring": 1,
    "mcp": 1,
    "cursor": 1,
    "codex": 1,
    "claude": 1,
    "人工智能": 6,
    "大模型": 5,
    "生成式": 6,
    "深度合成": 9,
    "拟人化": 9,
    "陪伴": 8,
    "换脸": 10,
    "仿声": 9,
    "魔改": 8,
    "智能体": 5,
    "录取": 10,
    "通知书": 10,
    "开学": 8,
    "高考": 8,
    "志愿": 7,
    "豆包": 6,
    "通义": 6,
    "元宝": 5,
    "文心": 5,
    "混元": 5,
    "鸿蒙": 4,
    "微信": 5,
    "支付宝": 6,
    "网信办": 8,
    "工信部": 7,
    "教育部": 8,
    "套餐": 7,
    "客服": 5,
}


def normalize_title(title: str) -> str:
    return re.sub(r"[\W_]+", "", title.lower())


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


def historical_titles(*directories: Path) -> list[str]:
    titles: list[str] = []
    for directory in directories:
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    titles.append(line[2:].strip())
                    break
    return titles


def rank_signals(
    signals: list[SourceSignal],
    existing_titles: list[str],
    *,
    limit: int = 8,
) -> list[SourceSignal]:
    ranked: list[SourceSignal] = []
    for signal in signals:
        if any(title_similarity(signal.title, title) >= 0.78 for title in existing_titles):
            continue
        title = signal.title.lower()
        summary = signal.summary.lower()
        bonus = sum(
            weight * 2 if term in title else weight
            for term, weight in HIGH_VALUE_TERMS.items()
            if term in title or term in summary
        )
        ranked.append(signal.model_copy(update={"score": signal.score + bonus}))
    return sorted(ranked, key=lambda item: (item.score, item.published_at), reverse=True)[:limit]

