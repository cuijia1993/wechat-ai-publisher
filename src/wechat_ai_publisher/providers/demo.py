from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from wechat_ai_publisher.domain.models import (
    Article,
    ClaimRequirement,
    ContentPlan,
    EditorialReviewResult,
    EvidenceContract,
    EvidenceItem,
    Outline,
    ResearchCard,
    ReviewResult,
    TopicSelection,
    TopicBrief,
    VisualBlock,
    VisualPlan,
    VisualReviewResult,
)

T = TypeVar("T", bound=BaseModel)


class DemoProvider:
    """不访问网络的演示模型，用于验证流水线接线。"""

    def structured(self, *, system: str, user: str, response_model: type[T]) -> T:
        if response_model is TopicBrief:
            payload = json.loads(user)
            signal = payload["candidates"][0]
            evidence_id = f"source:{signal['id']}"
            value = TopicBrief(
                signal_id=signal["id"],
                decision="write",
                content_type="workplace_guide",
                title="AI 工具又出新功能，普通人应该马上跟进吗",
                primary_search_keyword="AI 工具",
                category="AI 提效",
                target_reader="希望用 AI 改善日常工作的知识工作者",
                reader_problem="新功能很多，却不知道哪些真正能节省时间",
                core_conclusion="先确认具体任务和失败代价，再用低风险工作验证新功能",
                differentiation="不复述新闻，用一个日常工作故事拆解采用判断",
                reusable_asset="AI 新功能采用检查清单",
                audience_scope="knowledge_worker",
                audience_fit_score=78,
                title_angle="problem_first",
                general_reader_value="即使没用过该工具，也能复用这套新功能判断方法。",
                prerequisite_knowledge=["使用过任意 AI 助手"],
                evidence_contract=EvidenceContract(
                    items=[
                        EvidenceItem(
                            id=evidence_id,
                            kind="official_source",
                            description=signal["title"],
                            source_url=signal["url"],
                            verified=True,
                        )
                    ],
                    claims=[
                        ClaimRequirement(
                            id="official-fact",
                            claim="官方来源包含本次版本变化信息",
                            required_kinds=["official_source"],
                            evidence_refs=[evidence_id],
                            supported=True,
                        )
                    ],
                    ready_to_write=True,
                ),
                reasoning="官方来源清晰，并能转化为多数知识工作者可用的判断清单",
            )
        elif response_model is TopicSelection:
            payload = json.loads(user)
            signal = payload["candidates"][0]
            value = TopicSelection(
                signal_id=signal["id"],
                title=f"{signal['source_name']} 新变化：普通人应该马上跟进吗",
                category="AI 提效",
                target_reader="希望用 AI 改善工作的知识工作者",
                reader_problem="新功能很多，但不知道哪些值得投入时间",
                core_conclusion="先依据官方来源确认变化，再用低风险任务验证",
                required_evidence=["官方发布说明"],
                product_hook="版本验证检查清单",
                reasoning="官方来源明确且可以沉淀为通用采用清单",
            )
        elif response_model is ResearchCard:
            payload = json.loads(user)
            topic_payload = payload.get("topic", payload)
            contract = topic_payload.get("evidence_contract") or {}
            claim_evidence = {
                claim["id"]: claim.get("evidence_refs", [])
                for claim in contract.get("claims", [])
            }
            value = ResearchCard(
                topic_id="demo",
                target_reader="日常使用 AI 的知识工作者",
                reader_problem="AI 能快速生成内容，但结果是否可靠仍需判断",
                core_conclusion="AI 负责生成候选，人负责事实、取舍和边界",
                facts=["演示模式未调用外部模型"],
                evidence=["已提供验证记录"],
                claim_evidence=claim_evidence,
                risks=["演示内容不可直接发布"],
                ready_to_write=True,
            )
        elif response_model is ContentPlan:
            payload = json.loads(user)
            contract = payload.get("topic", {}).get("evidence_contract") or {}
            claim_ids = [claim["id"] for claim in contract.get("claims", [])]
            value = ContentPlan(
                title_candidates=[
                    "AI 工具又出新功能，别急着改变工作习惯",
                    "新功能发布后，普通人先检查这 5 项",
                ],
                recommended_title="AI 工具又出新功能，别急着改变工作习惯",
                digest="从一个日常工作场景出发，判断 AI 新功能是否真的值得采用。",
                thesis="新功能只有转化成具体任务和验证步骤，才会带来真实效率",
                sections=[
                    "具体变化",
                    "常见误区",
                    "验证步骤",
                    "限制与风险",
                    "可复制清单",
                ],
                evidence_to_use=["官方发布说明"],
                claim_ids_to_use=claim_ids,
                risks=["演示模式不代表真实版本结论"],
                reader_takeaway="一份普通人也能使用的 AI 新功能采用清单",
                story_hook="周一早上，小林看到 AI 上线会议整理功能，试用后发现迁移和核对同样花时间。",
                concrete_example="用一场脱敏会议比较原做法与新功能，检查决定、负责人和截止时间。",
                failure_or_twist="功能生成了完整纪要，却没有突出团队真正需要的三条待办。",
                plain_language_explanations={
                    "AI 工作流": "把任务拆成准备、生成、核对和采用四步"
                },
            )
        elif response_model is VisualPlan:
            value = VisualPlan(
                cover_subtitle="把版本变化转化成可执行验证步骤",
                blocks=[
                    VisualBlock(
                        id="workflow",
                        kind="flowchart",
                        anchor="AI 工作流设计",
                        title="先验证，再采用",
                        description="把模型输出放进受控验证链路",
                        items=["定义边界", "生成候选", "独立验证", "人工确认"],
                    ),
                    VisualBlock(
                        id="verification",
                        kind="checklist",
                        anchor="操作与验证过程",
                        title="验证链路检查清单",
                        items=["配置可追溯", "结论有证据", "门禁可阻断", "草稿可回滚"],
                    ),
                ],
            )
        elif response_model is Outline:
            value = Outline(
                title="AI 工具又出新功能，别急着改变工作习惯",
                digest="从一个日常工作场景出发，判断新功能是否真的值得采用。",
                sections=[
                    "遇到的具体问题",
                    "AI 工作流设计",
                    "操作与验证过程",
                    "人工确认点",
                    "可复制模板",
                ],
            )
        elif response_model is Article:
            payload = json.loads(user)
            if "plan" in payload:
                title = payload["plan"]["recommended_title"]
                digest = payload["plan"]["digest"]
            elif "article" in payload:
                title = payload["article"]["title"]
                digest = payload["article"]["digest"]
            else:
                title = "AI 工具又出新功能，别急着改变工作习惯"
                digest = "从一个日常工作场景出发，判断新功能是否真的值得采用。"
            markdown = f"""# {title}

## 遇到的具体问题

周一早上，小林看到常用 AI 工具上线了“自动整理会议”功能。他花了半小时迁移录音和提示词，最后发现团队真正需要的只是三条待办。

这是一个虚构的演示场景，但问题很常见：新功能看起来省事，学习、迁移和核对同样需要时间。

## AI 工作流设计

先选一场低风险会议，明确需要输出的决定、负责人和截止时间，再让 AI 生成候选纪要。人只核对事实和遗漏，不重新润色整篇文档。

## 操作与验证过程

可以拿同一份脱敏材料比较原来的做法和新功能：分别记录准备、生成、核对所需时间，并检查是否漏掉关键决定。

本地演示没有执行这项比较，因此这里只提供验证方法，不声称新功能已经节省了时间。

## 人工确认点

涉及客户信息、员工评价和未公开决策的材料不要直接上传。会议结论、负责人和截止时间仍需参会者确认。

## 可复制模板

采用新功能前先问四个问题：它替代了哪一步？迁移成本是多少？出错后谁核对？不用它会损失什么？四个问题答不清，就先别改工作习惯。
"""
            value = Article(
                topic_id="demo",
                title=title,
                digest=digest,
                markdown=markdown,
                author="智效进化论",
                publication_status="demo",
            )
        elif response_model is ReviewResult:
            value = ReviewResult(role="demo_reviewer", passed=True, issues=[])
        elif response_model is EditorialReviewResult:
            value = EditorialReviewResult(
                passed=True,
                overall_score=9,
                scores={
                    "factual_accuracy": 9,
                    "evidence_density": 9,
                    "actionability": 9,
                    "readability": 9,
                },
            )
        elif response_model is VisualReviewResult:
            value = VisualReviewResult(
                passed=True,
                overall_score=9,
                scores={
                    "content_consistency": 9,
                    "information_value": 9,
                    "legibility": 9,
                    "visual_consistency": 9,
                },
            )
        else:
            raise TypeError(f"演示模型不支持响应类型：{response_model.__name__}")
        return value  # type: ignore[return-value]

    def structured_with_images(
        self,
        *,
        system: str,
        user: str,
        image_paths: list[Path],
        response_model: type[T],
    ) -> T:
        if response_model is VisualReviewResult:
            value = VisualReviewResult(
                passed=True,
                overall_score=9,
                scores={
                    "content_consistency": 9,
                    "information_value": 9,
                    "legibility": 9,
                    "visual_consistency": 9,
                },
            )
            return value  # type: ignore[return-value]
        return self.structured(system=system, user=user, response_model=response_model)

