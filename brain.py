"""LLM reasoning module for scam-vs-genuine freebie classification."""

from __future__ import annotations

from typing import Literal

from anthropic import Anthropic
from openai import OpenAI

from config import Config

Decision = Literal["TRUE", "FALSE"]


class DealBrain:
    """Agentic decision engine backed by OpenAI or Anthropic models."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.provider = config.llm_provider
        self.openai_client = (
            OpenAI(api_key=config.openai_api_key) if config.openai_api_key else None
        )
        self.anthropic_client = (
            Anthropic(api_key=config.anthropic_api_key)
            if config.anthropic_api_key
            else None
        )

    @staticmethod
    def keyword_prefilter(title: str, description: str) -> bool:
        """Quick heuristic filter before spending tokens on LLM reasoning."""
        haystack = f"{title}\n{description}".lower()
        keywords = ["free", "gift card", "$0", "100% off", "no cost"]
        return any(keyword in haystack for keyword in keywords)

    def _prompt(self, title: str, description: str) -> str:
        """
        Build strict TRUE/FALSE prompt for the reasoning step.

        Reasoning Step:
            The model decides if the post is a genuine free item/gift card,
            rejecting deceptive discount mechanics (e.g. BOGO, conditional spend).
        """
        return (
            "You are a strict deal-classification agent.\n"
            "Classify if the following OzBargain post is a genuine free item "
            "or genuine free gift card.\n"
            "Reject offers that are discounts, bundle requirements, "
            "'buy one get one', spend-threshold freebies, or trials requiring "
            "payment details.\n\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            "Is this a genuine free item/gift card or just a scam/discount?\n"
            "Answer ONLY 'TRUE' or 'FALSE'."
        )

    def _classify_openai(self, title: str, description: str) -> Decision:
        if not self.openai_client:
            raise RuntimeError("OPENAI_API_KEY is missing.")
        prompt = self._prompt(title, description)
        response = self.openai_client.responses.create(
            model=self.config.openai_model,
            input=prompt,
            max_output_tokens=5,
        )
        text = response.output_text.strip().upper()
        return "TRUE" if "TRUE" in text else "FALSE"

    def _classify_anthropic(self, title: str, description: str) -> Decision:
        if not self.anthropic_client:
            raise RuntimeError("ANTHROPIC_API_KEY is missing.")
        prompt = self._prompt(title, description)
        response = self.anthropic_client.messages.create(
            model=self.config.anthropic_model,
            max_tokens=5,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in response.content:
            if getattr(block, "type", "") == "text":
                text += block.text
        text = text.strip().upper()
        return "TRUE" if "TRUE" in text else "FALSE"

    def classify(self, title: str, description: str) -> Decision:
        """Route classification to selected provider."""
        # Fallback mode for environments without LLM credentials.
        if self.provider == "openai" and not self.openai_client:
            return "TRUE"
        if self.provider == "anthropic" and not self.anthropic_client:
            return "TRUE"
        if self.provider == "anthropic":
            return self._classify_anthropic(title, description)
        return self._classify_openai(title, description)
