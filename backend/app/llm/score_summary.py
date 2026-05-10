from __future__ import annotations

from functools import lru_cache
import re
from typing import Any

from app.llm.client import LLMError, chat_json


def _short_downward_factor(value: str) -> str:
    normalized = value.strip().casefold().replace("_", " ")
    if "distance" in normalized and "home" in normalized:
        return "home distance"
    if "territory" in normalized:
        return "territory fit"
    return value.strip()


def _plain_order_range(value: str) -> str:
    return value.replace("-", " to ")


def _fallback_bullets(reasons: tuple[str, ...], limit: int) -> list[str]:
    previous_visit: str | None = None
    visit_count: str | None = None
    order_gap: str | None = None
    order_value: str | None = None
    nearby: str | None = None
    downward: list[str] = []
    other: list[str] = []

    for reason in reasons:
        clean = reason.strip()
        if not clean:
            continue
        lowered = clean.lower()
        if lowered.startswith("downward factor:"):
            downward.append(_short_downward_factor(clean.removeprefix("Downward factor:").strip().rstrip(".")))
        elif "previous visit outcome" in lowered:
            previous_visit = clean
        elif "has been visited" in lowered:
            visit_count = clean
        elif "not placed an order" in lowered:
            order_gap = clean
        elif "historical order value" in lowered or "usual order value" in lowered:
            order_value = clean
        elif "nearby customers" in lowered:
            nearby = clean
        else:
            other.append(clean)

    grouped: list[str] = []
    if previous_visit and visit_count:
        visit_numbers = sorted(_numeric_tokens(visit_count))
        visit_phrase = f"visited them {visit_numbers[0]} times" if visit_numbers else "visited them before"
        grouped.append(f"You have {visit_phrase}, so RouteIQ uses that relationship history.")
    elif previous_visit:
        grouped.append("RouteIQ uses the last visit outcome to judge follow-up potential.")
    elif visit_count:
        visit_numbers = sorted(_numeric_tokens(visit_count))
        grouped.append(
            f"You have visited them {visit_numbers[0]} times before." if visit_numbers else "You have visited them before."
        )

    order_parts: list[str] = []
    if order_gap:
        order_numbers = sorted(_numeric_tokens(order_gap))
        if order_numbers:
            order_parts.append(f"no order for {order_numbers[0]} days")
    if order_value:
        order_ranges = sorted(token for token in _numeric_tokens(order_value) if token.upper().startswith("RM"))
        if order_ranges:
            order_parts.append(f"past orders are {_plain_order_range(order_ranges[0])}")
    if order_parts:
        grouped.append(f"Worth checking in: {' and '.join(order_parts)}.")

    coverage_parts = [part for part in [nearby] if part]
    if downward:
        coverage_parts.append(f"Downward factors: {', '.join(downward)}.")
    if coverage_parts:
        nearby_numbers = sorted(_numeric_tokens(nearby or ""))
        nearby_text = (
            f"There are {nearby_numbers[0]} nearby customers, so it fits the route"
            if nearby_numbers
            else "Nearby customers make this easier to fit into the route"
        )
        downward_text = f", but {', '.join(downward)} make it slightly less ideal" if downward else ""
        grouped.append(f"{nearby_text}{downward_text}.")

    grouped.extend(other)
    return grouped[:limit]


def _numeric_tokens(text: str) -> set[str]:
    normalized = text.replace("–", "-").replace("—", "-")
    return set(re.findall(r"RM\d+k(?:-RM\d+k)?|\d+(?:\.\d+)?", normalized, flags=re.IGNORECASE))


def _keeps_numeric_facts(original_text: str, bullets: list[str]) -> bool:
    source_numbers = _numeric_tokens(original_text)
    if not source_numbers:
        return True
    bullet_numbers = _numeric_tokens(" ".join(bullets))
    return source_numbers.issubset(bullet_numbers)


def _keeps_downward_facts(reasons: tuple[str, ...], bullets: list[str]) -> bool:
    downward_terms = [
        reason.removeprefix("Downward factor:").strip().rstrip(".").casefold()
        for reason in reasons
        if reason.casefold().startswith("downward factor:")
    ]
    if not downward_terms:
        return True
    bullet_text = " ".join(bullets).casefold()
    return "downward" in bullet_text and all(term in bullet_text for term in downward_terms)


def _clean_bullet(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lstrip("-*•0123456789. ").strip()
    if not cleaned:
        return None
    return cleaned


@lru_cache(maxsize=256)
def summarize_score_reasons(reasons: tuple[str, ...], limit: int = 3) -> list[str]:
    """Use the local LLM to compress score reasons into short UI bullets."""
    clean_reasons = tuple(reason.strip() for reason in reasons if reason.strip())
    if not clean_reasons:
        return []

    limit = max(1, min(limit, 3))
    original_text = " ".join(clean_reasons)
    source_lines = "\n".join(f"- {reason}" for reason in clean_reasons)
    required_numbers = ", ".join(sorted(_numeric_tokens(original_text))) or "none"
    system_prompt = (
        "You summarize CRM scoring explanations for a Hilti sales app. "
        "Return only JSON with a `bullets` array. Use at most 3 bullets. "
        "Preserve all important facts and numbers. Do not invent facts. "
        "Do not add advice, recommendations, competitors, or other salespeople unless explicitly present. "
        "Use plain salesperson language. Avoid model jargon such as downward factor, territory id, estimate, or likelihood. "
        "Each bullet should explain why the salesperson should care, in under 18 words. "
        "Combine related reasons, especially repeated visit-likelihood wording and downward factors. "
        "Represent every source reason somewhere in the bullets. "
        "Keep downward factors separate; do not label prior visits as downward unless the source says so. "
        "For nearby-customer facts, say they indicate route density or area coverage only."
    )
    user_prompt = (
        f"Convert these factual source reasons into at most {limit} bullet points.\n"
        f"Required numeric tokens to include exactly where relevant: {required_numbers}\n\n"
        "Use this grouping where applicable:\n"
        "1. Relationship history: previous visit outcome and prior visit count.\n"
        "2. Sales opportunity: days since last order and order value range.\n"
        "3. Route practicality: nearby customer density, with any score-lowering travel/territory factors.\n\n"
        f"Source reasons:\n{source_lines}"
    )

    try:
        payload = chat_json(system_prompt, user_prompt, temperature=0.0)
    except LLMError:
        return _fallback_bullets(clean_reasons, limit)

    raw_bullets = payload.get("bullets")
    if not isinstance(raw_bullets, list):
        return _fallback_bullets(clean_reasons, limit)

    bullets: list[str] = []
    seen: set[str] = set()
    for raw in raw_bullets:
        cleaned = _clean_bullet(raw)
        if cleaned is None:
            continue
        normalized = cleaned.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        bullets.append(cleaned)
        if len(bullets) >= limit:
            break

    if (
        bullets
        and _keeps_numeric_facts(original_text, bullets)
        and _keeps_downward_facts(clean_reasons, bullets)
    ):
        return bullets

    retry_prompt = (
        f"Your previous summary missed required facts. Rewrite into at most {limit} bullets. "
        "Copy every number and RM range from the original exactly. "
        "Include the downward factors as downward factors. Return only JSON.\n\n"
        f"Required numeric tokens: {required_numbers}\n\n"
        f"Original explanation:\n{original_text}\n\n"
        f"Previous bullets:\n{bullets}"
    )
    try:
        retry_payload = chat_json(system_prompt, retry_prompt, temperature=0.0)
    except LLMError:
        return _fallback_bullets(clean_reasons, limit)

    retry_raw = retry_payload.get("bullets")
    if not isinstance(retry_raw, list):
        return _fallback_bullets(clean_reasons, limit)

    retry_bullets: list[str] = []
    seen.clear()
    for raw in retry_raw:
        cleaned = _clean_bullet(raw)
        if cleaned is None:
            continue
        normalized = cleaned.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        retry_bullets.append(cleaned)
        if len(retry_bullets) >= limit:
            break

    if (
        retry_bullets
        and _keeps_numeric_facts(original_text, retry_bullets)
        and _keeps_downward_facts(clean_reasons, retry_bullets)
    ):
        return retry_bullets
    return _fallback_bullets(clean_reasons, limit)
