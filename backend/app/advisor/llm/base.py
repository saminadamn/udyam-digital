from typing import Protocol


class LLMProvider(Protocol):
    name: str

    def phrase_question(self, field: str, lang: str, profile: dict, default: str) -> str:
        """Return the next question in the user's language. Must stay one short question."""

    def extract(self, field: str, content: str, lang: str, profile: dict) -> dict | None:
        """Pull a profile field out of free text the deterministic parser could not read. None = not understood."""

    def choose(self, profile: dict, eligible: list[dict], suggested: dict) -> dict | None:
        """Pick product ids from `eligible` only: {"core": [...], "addons": [...]}. None = keep the suggestion."""

    def explain(self, context: dict, lang: str, default: str) -> str:
        """2-3 plain sentences in the user's language. Only the products and total in `context`."""


def get_provider() -> LLMProvider:
    from app.config import get_settings

    s = get_settings()
    if s.llm_provider in ("openai", "openai_compatible") and s.llm_api_key:
        from app.advisor.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(s.llm_base_url, s.llm_api_key, s.llm_model or "gpt-4o-mini", s.llm_timeout_s)
    from app.advisor.llm.template import TemplateProvider

    return TemplateProvider()
