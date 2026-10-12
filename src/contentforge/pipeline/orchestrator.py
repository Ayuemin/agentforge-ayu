"""Pipeline orchestrator — coordinates all 8 agents in sequence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..agents import AGENT_REGISTRY, get_agent
from ..agents.base import AgentResult
from ..core.config import ContentForgeConfig
from ..core.mimo_client import MiMoClient
from ..core.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Final result from the complete pipeline."""

    status: str = "success"
    article: str = ""
    research: str = ""
    outline: str = ""
    seo_analysis: str = ""
    quality_report: str = ""
    publisher_output: str = ""
    editorial_audit: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    failed_stage: str = ""
    quality_score: float = 0.0
    translations: dict[str, str] = field(default_factory=dict)
    agent_results: dict[str, AgentResult] = field(default_factory=dict)
    metrics_path: str = ""
    total_tokens: int = 0
    pipeline_duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == "success"

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "total_tokens": self.total_tokens,
            "pipeline_duration_s": round(self.pipeline_duration_s, 2),
            "agents_run": list(self.agent_results.keys()),
            "article_length": len(self.article),
            "word_count": len(self.article.split()),
            "translations": list(self.translations.keys()),
            "metrics_path": self.metrics_path,
            "editorial_audit": self.editorial_audit,
            "error_message": self.error_message,
            "failed_stage": self.failed_stage,
            "quality_score": self.quality_score,
        }


class PipelineOrchestrator:
    """Coordinates all 8 ContentForge agents in sequence.

    Pipeline flow:
    1. Research → gather information
    2. Outline → structure content
    3. Writer → generate draft
    4. SEO → analyze optimization opportunities
    5. Editor → refine and polish (incorporates SEO suggestions)
    6. Quality → fact-check and score
    7. Translator → adapt to target languages (if enabled)
    8. Publisher → format and export

    Supports iterative refinement: if Quality score < threshold,
    re-run Editor → Quality loop up to max_iterations times.
    """

    AGENT_ORDER = [
        "research",
        "outline",
        "writer",
        "seo",
        "editor",
        "quality",
        "translator",
        "publisher",
    ]

    def __init__(self, config: ContentForgeConfig):
        self.config = config
        self.tracker = TokenTracker(output_dir=config.output_dir)
        self._client: Optional[MiMoClient] = None

    async def run(self, topic: str, *, research_context: str = "", **kwargs) -> PipelineResult:
        """Execute the full pipeline for a given topic."""
        result = PipelineResult()

        self.tracker.start_pipeline()
        steps = Path(self.config.output_dir)
        steps.mkdir(parents=True, exist_ok=True)

        def snapshot(name: str, text: str) -> None:
            (steps / name).write_text(text, encoding="utf-8")

        def require_success(stage: str, item: AgentResult) -> None:
            if item.ok:
                return
            result.failed_stage = stage
            result.error_message = item.error or "Агент завершился без результата."
            raise RuntimeError(result.error_message)

        async with MiMoClient(self.config.mimo) as client:
            self._client = client

            try:
                # Step 1: Research
                logger.info("[Pipeline] Step 1/8: Research")
                research_agent = get_agent(
                    "research", config=self.config, client=client, tracker=self.tracker
                )
                research_result = await research_agent.run(topic=topic, source_context=research_context)
                result.agent_results["research"] = research_result
                result.research = research_result.content
                snapshot("01_research.json", research_result.content)

                require_success("research", research_result)

                # Step 2: Outline
                logger.info("[Pipeline] Step 2/8: Outline")
                outline_agent = get_agent(
                    "outline", config=self.config, client=client, tracker=self.tracker
                )
                outline_result = await outline_agent.run(
                    research_data=research_result.content,
                    target_words=self.config.pipeline.target_word_count,
                )
                result.agent_results["outline"] = outline_result
                result.outline = outline_result.content
                snapshot("02_outline.json", outline_result.content)

                require_success("outline", outline_result)

                # Step 3: Writer
                logger.info("[Pipeline] Step 3/8: Writer")
                writer_agent = get_agent(
                    "writer", config=self.config, client=client, tracker=self.tracker
                )
                writer_result = await writer_agent.run(
                    outline=outline_result.content,
                    research_data=research_result.content,
                    language=self.config.pipeline.language,
                )
                result.agent_results["writer"] = writer_result
                current_content = writer_result.content
                snapshot("03_writer.md", current_content)
                require_success("writer", writer_result)

                # Step 4: SEO Analysis
                logger.info("[Pipeline] Step 4/8: SEO")
                seo_agent = get_agent(
                    "seo", config=self.config, client=client, tracker=self.tracker
                )
                seo_result = await seo_agent.run(content=current_content)
                result.agent_results["seo"] = seo_result
                result.seo_analysis = seo_result.content
                snapshot("04_seo.json", seo_result.content)
                require_success("seo", seo_result)

                # Step 5 + 6: Editor → Quality loop
                dzen_mode = self.config.pipeline.editorial_profile == "dzen"
                previous_feedback = ""
                for iteration in range(self.config.pipeline.max_iterations):
                    logger.info(f"[Pipeline] Step 5/8: Editor (iteration {iteration + 1})")
                    editor_agent = get_agent(
                        "editor", config=self.config, client=client, tracker=self.tracker
                    )
                    editor_result = await editor_agent.run(
                        content=current_content,
                        seo_recommendations=seo_result.content,
                        editorial_feedback=previous_feedback if dzen_mode else "",
                    )
                    result.agent_results["editor"] = editor_result
                    current_content = editor_result.content
                    snapshot(f"05_editor_{iteration + 1}.md", current_content)
                    require_success("editor", editor_result)

                    logger.info(f"[Pipeline] Step 6/8: Quality (iteration {iteration + 1})")
                    quality_agent = get_agent(
                        "quality", config=self.config, client=client, tracker=self.tracker
                    )
                    quality_result = await quality_agent.run(
                        content=current_content,
                        threshold=self.config.pipeline.quality_threshold,
                        title=topic,
                    )
                    result.agent_results["quality"] = quality_result
                    result.quality_report = quality_result.content
                    snapshot(f"06_quality_{iteration + 1}.json", quality_result.content)
                    require_success("quality", quality_result)

                    # Original Quality JSON score remains in charge; the
                    # Dzen branch also checks actual readable character counts.
                    quality_score = quality_result.metadata.get("overall_score", 0)
                    result.quality_score = quality_score
                    threshold = self.config.pipeline.quality_threshold * 100
                    audit_ok = True
                    if dzen_mode:
                        from ..dzen_editorial import article_audit

                        p = self.config.pipeline
                        audit = article_audit(
                            current_content, p.min_chars, p.max_chars, p.title_max_chars
                        )
                        audit["quality_score"] = quality_score
                        audit["quality_threshold"] = threshold
                        audit["quality_parse_error"] = (
                            quality_result.metadata.get("score_parse_error", "")
                        )
                        result.editorial_audit = audit
                        snapshot("07_dzen_audit.json", json.dumps(
                            audit, ensure_ascii=False, indent=2
                        ))
                        audit_ok = audit["passed"]
                        messages = list(audit["issues"])
                        if audit["quality_parse_error"]:
                            messages.append(audit["quality_parse_error"])
                        try:
                            reviewed = json.loads(quality_result.content)
                            if isinstance(reviewed, dict):
                                for key in ("factual_issues", "logical_inconsistencies",
                                            "improvement_suggestions"):
                                    notes = reviewed.get(key, [])
                                    if isinstance(notes, list):
                                        messages.extend(str(note) for note in notes[:4])
                        except (ValueError, TypeError):
                            messages.append("Не удалось прочитать JSON замечаний Quality.")
                        previous_feedback = "\n".join(messages[:14])
                    if quality_score >= threshold and audit_ok:
                        logger.info(
                            f"[Pipeline] Quality score {quality_score} >= {threshold}, passing"
                        )
                        break
                    elif iteration < self.config.pipeline.max_iterations - 1:
                        logger.info(
                            f"[Pipeline] Quality score {quality_score} < {threshold}, "
                            f"re-editing (iteration {iteration + 2})"
                        )

                result.article = current_content
                if dzen_mode and (not result.editorial_audit.get("passed", False) or quality_score < threshold):
                    result.status = "needs_review"
                    snapshot("НЕГОТОВО_требует_правки.md", current_content)
                    snapshot("ЧЕРНОВИК.md", current_content)

                # Step 7: Translation (if enabled)
                if self.config.pipeline.enable_translation:
                    logger.info("[Pipeline] Step 7/8: Translation")
                    translator_agent = get_agent(
                        "translator", config=self.config, client=client, tracker=self.tracker
                    )
                    for lang in self.config.pipeline.target_languages:
                        trans_result = await translator_agent.run(
                            content=current_content,
                            target_language=lang,
                        )
                        result.translations[lang] = trans_result.content
                        result.agent_results[f"translator_{lang}"] = trans_result
                else:
                    logger.info("[Pipeline] Step 7/8: Translation (skipped, disabled)")

                # Step 8: Publisher
                logger.info("[Pipeline] Step 8/8: Publisher")
                publisher_agent = get_agent(
                    "publisher", config=self.config, client=client, tracker=self.tracker
                )
                publisher_result = await publisher_agent.run(
                    content=current_content,
                    title=topic,
                    publish_targets=self.config.pipeline.publish_targets,
                    output_dir=self.config.output_dir,
                )
                result.agent_results["publisher"] = publisher_result
                result.publisher_output = publisher_result.content
                snapshot("08_publisher.json", publisher_result.content)

            except Exception as e:
                from ..core.request_errors import describe_error

                message = result.error_message or describe_error(e, timeout=self.config.llm.timeout)
                result.error_message = message
                logger.error("[Pipeline] Ошибка на этапе %s: %s",
                             result.failed_stage or "unknown", message)
                result.status = "failed"
            finally:
                self.tracker.end_pipeline()
                result.total_tokens = self.tracker.total_tokens
                result.pipeline_duration_s = self.tracker.pipeline_duration_s
                result.metrics_path = str(self.tracker.save())
                snapshot("run_status.json", json.dumps(result.summary(), ensure_ascii=False, indent=2))

        return result

    def get_agent_list(self) -> list[dict[str, str]]:
        """Return list of all available agents with descriptions."""
        return [
            {"name": name, "description": cls.description} for name, cls in AGENT_REGISTRY.items()
        ]
