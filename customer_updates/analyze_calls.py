#!/usr/bin/env python3
"""Summarize a SpeakSport call CSV and surface candidate proof calls."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


SUCCESS_PATTERNS = (
    r"\b(?:you(?:'re| are)|it(?:'s| is)|that(?:'s| is)) (?:all )?(?:set|booked|confirmed)\b",
    r"\b(?:booking|reservation|tee time) (?:has been|is) confirmed\b",
    r"\bconfirmation (?:number|email)\b",
)

ELIGIBILITY_PATTERNS = (
    r"\beligib(?:le|ility)\b",
    r"\bactive (?:eligible )?account\b",
    r"\bnot (?:able|eligible) to book\b",
)

LOOKUP_PATTERNS = (
    r"\bupcoming booking",
    r"\bexisting (?:booking|reservation)",
    r"\bfind (?:your|the) (?:booking|reservation)",
)

CANCELLATION_PATTERNS = (
    r"\bcancel(?:lation|led|ing)?\b",
    r"\bremove (?:the|your) (?:booking|reservation|tee time)\b",
)

INFO_PATTERNS = (
    r"\b(?:rate|price|cost|fee)s?\b",
    r"\b(?:open|close|hours)\b",
    r"\b(?:membership|member)\b",
    r"\b(?:weather|rain|cart path)\b",
    r"\b(?:league|tournament|outing)\b",
)

BOOKING_LINK_OFFERED_PATTERNS = (
    r"\bsend (?:you )?(?:a )?text (?:message )?(?:with )?(?:the|a) link\b",
    r"\btext (?:you )?(?:the|a) (?:direct )?(?:booking )?link\b",
    r"\bsend (?:the|that|a) (?:booking )?link\b",
)

BOOKING_LINK_SENT_PATTERNS = (
    r"\bi(?:'ve| have) just sent (?:that|the) link\b",
    r"\bjust sent (?:that|the) link\b",
    r"\blink (?:has been|was) sent\b",
)

BOOKING_INTENT_PATTERNS = (
    r"\bbook(?:ing)?\b",
    r"\breserv(?:e|ation|ing)\b",
    r"\btee time\b",
    r"\bplay golf\b",
)

CORRECT_NEXT_ACTION_PATTERNS = (
    *BOOKING_LINK_OFFERED_PATTERNS,
    *BOOKING_LINK_SENT_PATTERNS,
    r"\btransferr?ing you to (?:the )?(?:golf|pro) shop\b",
    r"\btransfer you to (?:the )?(?:golf|pro) shop\b",
)


def matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def compact_transcript(text: str, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def analyze(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError(f"No call rows found in {path}")

    durations = [int(row.get("duration_ms") or 0) for row in rows]
    candidates: dict[str, list[dict]] = {
        "booking_success": [],
        "eligibility_verification": [],
        "booking_lookup": [],
        "cancellation": [],
        "information_answered": [],
        "booking_link_offered": [],
        "booking_link_sent": [],
        "booking_intent_routed": [],
    }

    for row in rows:
        transcript = row.get("transcript", "")
        record = {
            "call_id": row.get("call_id"),
            "date": row.get("call_date"),
            "time": row.get("call_time"),
            "duration": row.get("duration"),
            "ended_reason": row.get("ended_reason"),
            "transcript": compact_transcript(transcript),
        }
        if matches_any(transcript, SUCCESS_PATTERNS):
            candidates["booking_success"].append(record)
        if matches_any(transcript, ELIGIBILITY_PATTERNS):
            candidates["eligibility_verification"].append(record)
        if matches_any(transcript, LOOKUP_PATTERNS):
            candidates["booking_lookup"].append(record)
        if matches_any(transcript, CANCELLATION_PATTERNS):
            candidates["cancellation"].append(record)
        if matches_any(transcript, INFO_PATTERNS) and "AI:" in transcript:
            candidates["information_answered"].append(record)
        if matches_any(transcript, BOOKING_LINK_OFFERED_PATTERNS):
            candidates["booking_link_offered"].append(record)
        if matches_any(transcript, BOOKING_LINK_SENT_PATTERNS):
            candidates["booking_link_sent"].append(record)
        if matches_any(transcript, BOOKING_INTENT_PATTERNS) and matches_any(
            transcript, CORRECT_NEXT_ACTION_PATTERNS
        ):
            candidates["booking_intent_routed"].append(record)

    return {
        "source": str(path),
        "period": {
            "start": min(row["call_date"] for row in rows),
            "end": max(row["call_date"] for row in rows),
        },
        "calls": len(rows),
        "total_duration_minutes": round(sum(durations) / 60000, 1),
        "average_duration_seconds": round(sum(durations) / max(len(durations), 1) / 1000, 1),
        "ended_reason": dict(Counter(row.get("ended_reason") for row in rows)),
        "candidate_counts": {key: len(value) for key, value in candidates.items()},
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = analyze(args.csv_path)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
