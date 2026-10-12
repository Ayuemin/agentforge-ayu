"""Base agent class with MiMo integration and metrics tracking."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.request_errors import describe_error
from ..core.config import ContentForgeConfig
from ..core.mimo_client import ChatMessage, ChatResponse, MiMoClient
from ..core.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Standardized result from any agent."""

    agent_name: str
    status: str = "success"  # success | partial | failed
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    reasoning: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "success"


class BaseAgent(ABC):
    """Abstract base for all ContentForge agents.

    Each agent:
    - Has a unique name and role description
    - Communicates with MiMo V2.5 Pro via the shared client
    - Reports metrics to the global TokenTracker
    - Supports system prompt customization via config
    """

    name: str = "base"
    description: str = "Base agent"
    system_prompt: str = "You are a helpful AI assistant."

    def __init__(
        self,
        config: ContentForgeConfig,
        client: MiMoClient,
        tracker: TokenTracker,
    ):
        self.config = config
        self.client = client
        self.tracker = tracker
        self._agent_config = config.get_agent_config(self.name)
        self._iteration = 0

    @property
    def effective_system_prompt(self) -> str:
        if self._agent_config.system_prompt_override:
            return self._agent_config.system_prompt_override
        return self.system_prompt

    async def _call_mimo(
        self,
        user_prompt: str,
        *,
        context: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """Make a call to MiMo API with the agent's system prompt."""
        system_content = self.effective_system_prompt
        if self.name != "translator" and self.config.pipeline.language == "ru":
            system_content += (
                "\n\nOutput language: Russian (ru). Use natural Russian for all prose "
                "and JSON string values. Preserve the required JSON field names, "
                "code snippets, and technical identifiers."
            )
        if self.config.pipeline.editorial_profile == "dzen":
            from ..dzen_editorial import stage_guidance

            p = self.config.pipeline
            system_content += "\n\n" + stage_guidance(
                self.name, p.min_chars, p.target_chars, p.max_chars, p.title_max_chars
            )
        if self.config.pipeline.editorial_profile == "dzen":
            skill_context = self.config._skill_texts.get(self.name, "")
            if skill_context:
                system_content += "\n\n" + skill_context
        messages = [ChatMessage(role="system", content=system_content)]

        if context:
            messages.append(ChatMessage(role="user", content=f"Context:\n{context}"))

        if self._agent_config.user_prompt_addition:
            user_prompt += "\n\nДополнительные инструкции редакционного профиля:\n" + (
                self._agent_config.user_prompt_addition
            )
        if (
            self.config.pipeline.editorial_profile == "dzen"
            and self.config._article_brief
            and self.name in {"outline", "writer", "seo", "editor", "quality", "publisher"}
        ):
            # Always retain the user's exact request. An outline is a proposed
            # structure, not permission to silently change an article's genre.
            user_prompt += (
                "\n\nИЗНАЧАЛЬНОЕ ЗАДАНИЕ АВТОРА (обязательно сохранить цель):\n"
                + self.config._article_brief
                + "\n\nНельзя подменять запрошенный жанр другим. Если заказан "
                "обзор и сравнение конкретных решений, нужны их реальные "
                "различия, преимущества и недостатки. Чек-лист можно добавить "
                "только как дополнение, а не вместо сравнения. Факты не выдумывай."
            )
        messages.append(ChatMessage(role="user", content=user_prompt))

        start = time.monotonic()
        try:
            response = await self.client.chat(
                messages,
                model=self._agent_config.model_override,
                temperature=temperature or self._agent_config.temperature_override,
                max_tokens=max_tokens if max_tokens is not None else self._agent_config.max_tokens_override,
                reasoning_effort=self._agent_config.reasoning_effort_override,
            )
            latency = (time.monotonic() - start) * 1000

            self.tracker.record(
                agent_name=self.name,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                latency_ms=latency,
                cached_tokens=response.usage.cached_tokens,
            )

            return response

        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            self.tracker.record(
                agent_name=self.name,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency,
                errors=1,
            )
            logger.error("Агент %s: %s", self.name, describe_error(e, timeout=self.config.llm.timeout))
            raise

    @abstractmethod
    async def execute(self, **kwargs) -> AgentResult:
        """Execute the agent's primary task. Must be implemented by subclasses."""
        ...

    async def run(self, **kwargs) -> AgentResult:
        """Run with error handling and metrics."""
        self._iteration += 1
        logger.info(f"[{self.name}] Starting iteration {self._iteration}")

        try:
            result = await self.execute(**kwargs)
            logger.info(
                f"[{self.name}] Completed: {result.status} "
                f"({result.tokens_used} tokens, {result.latency_ms:.0f}ms)"
            )
            return result
        except Exception as e:
            logger.error("[%s] Failed: %s", self.name, describe_error(e, timeout=self.config.llm.timeout))
            return AgentResult(
                agent_name=self.name,
                status="failed",
                error=describe_error(e, timeout=self.config.llm.timeout),
            )
