from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from autopatch.orchestrator.tokens import PRICING_PER_MILLION


class CachedLLMResponse(BaseModel):
    """Stored completion and metadata for a cached LLM call."""
    cache_key: str
    prompt_hash: str = ""
    model: str
    response_text: str
    prompt_tokens: int
    completion_tokens: int
    cost_saved_usd: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hit_count: int = 1


def compute_cache_key(model: str, prompt: str, temperature: float = 0.0) -> str:
    """Computes a canonical SHA-256 cache key from model parameters and prompt."""
    raw = f"{model.strip()}:{temperature:.2f}:{prompt.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LLMCache:
    """
    Deterministic cache for LLM responses indexed by canonical input hash.
    Eliminates redundant inference spend, avoids flakiness, and enables deterministic replay.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, CachedLLMResponse] = {}
        self._total_requests: int = 0
        self._total_hits: int = 0
        self._total_misses: int = 0
        self._total_tokens_saved: int = 0
        self._total_cost_saved_usd: float = 0.0

    def get(self, model: str, prompt: str, temperature: float = 0.0) -> Optional[CachedLLMResponse]:
        """Retrieves a cached completion if an exact prompt hash match exists."""
        self._total_requests += 1
        key = compute_cache_key(model, prompt, temperature)
        cached = self._entries.get(key)
        if cached:
            self._total_hits += 1
            cached.hit_count += 1
            tokens_saved = cached.prompt_tokens + cached.completion_tokens
            self._total_tokens_saved += tokens_saved
            self._total_cost_saved_usd += cached.cost_saved_usd
            return cached
        self._total_misses += 1
        return None

    def put(
        self,
        model: str,
        prompt: str,
        response_text: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        temperature: float = 0.0,
    ) -> CachedLLMResponse:
        """Stores a completion in the cache."""
        key = compute_cache_key(model, prompt, temperature)
        prompt_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()

        pricing = PRICING_PER_MILLION.get(model, PRICING_PER_MILLION["default"])
        cost = (prompt_tokens / 1_000_000.0) * pricing["input"] + (completion_tokens / 1_000_000.0) * pricing["output"]

        entry = CachedLLMResponse(
            cache_key=key,
            prompt_hash=prompt_hash,
            model=model,
            response_text=response_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_saved_usd=round(cost, 6),
            created_at=datetime.now(timezone.utc),
            hit_count=1,
        )
        self._entries[key] = entry
        return entry

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry: requests, hits, hit_rate, and cost saved."""
        rate = (self._total_hits / self._total_requests * 100.0) if self._total_requests > 0 else 0.0
        return {
            "total_requests": self._total_requests,
            "hits": self._total_hits,
            "misses": self._total_misses,
            "hit_rate_pct": round(rate, 2),
            "tokens_saved": self._total_tokens_saved,
            "cost_saved_usd": round(self._total_cost_saved_usd, 6),
            "total_cached_entries": len(self._entries),
        }

    def clear(self) -> None:
        """Clears the cache."""
        self._entries.clear()
        self._total_requests = 0
        self._total_hits = 0
        self._total_misses = 0
        self._total_tokens_saved = 0
        self._total_cost_saved_usd = 0.0


# Shared global LLM cache instance
global_llm_cache = LLMCache()
