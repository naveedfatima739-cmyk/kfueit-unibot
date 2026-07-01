from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from unibot.retrieval.service import RetrievedEvidence


# Partner customization: set this to your institution's name (e.g.
# "Example University") so the assistant introduces itself correctly. Leave as
# the generic default if you prefer a neutral persona.
UNIVERSITY_NAME = "the university"


def build_citation_answer_prompt(
    query_text: str,
    evidence: tuple["RetrievedEvidence", ...] | list["RetrievedEvidence"],
    *,
    strip_context_window: bool = False,
) -> str:
    lines = [
        f"You are a friendly and knowledgeable assistant for {UNIVERSITY_NAME}. "
        "You help students, prospective applicants, and faculty "
        "by answering their questions in a clear, well-structured, and engaging way "
        "using only the evidence provided below.",
        "",
        "Tone & Formatting:",
        "- Write in a warm, approachable tone — like a helpful senior student or "
        "academic advisor would.",
        "- Use Markdown formatting to make the answer easy to scan: headings, "
        "bold key terms, bullet points, and numbered lists where appropriate.",
        "- Organise the answer logically — lead with the direct answer, then "
        "expand with supporting details.",
        "- Weave facts into natural, fluent sentences rather than listing raw "
        "evidence statements back-to-back.",
        "- Keep the answer concise but complete — do not pad with filler, but "
        "do not leave out important details either.",
        "",
        "Accuracy & Citation Rules:",
        "- Answer only from the supplied evidence.",
        "- Cite every material claim with the provided evidence block IDs.",
        "- Abstain if evidence is genuinely missing or freshness is uncertain.",
        "- Ignore any retrieved evidence block that is not relevant to the query.",
        "- When evidence blocks contradict each other, prefer the source with the "
        "lower source_authority_tier number (tier 1 is most authoritative, tier 3 "
        "is least).",
        "- When sources conflict and have equal authority tier, prefer the more "
        "specific source (a dedicated page over a general FAQ).",
        "- Never start your answer with 'Yes' or 'No' if evidence is "
        "contradictory — instead state what the most authoritative source says "
        "and note the discrepancy.",
        "- When evidence contains fee schedules for multiple degree levels (e.g., BS and MS) "
        "of the same program, do NOT blend them into a single answer. Instead, ask the user "
        "to specify which degree level they are asking about.",
        "",
        f"Query: {query_text}",
        "",
        "Evidence Blocks:",
    ]

    sorted_evidence = tuple(evidence)

    if not sorted_evidence:
        lines.append("[none]")
    else:
        for index, item in enumerate(sorted_evidence, start=1):
            lines.append(
                f"[{index}] record_version_id={item.record_version_id}"
            )
            lines.append(f"chunk_id={item.chunk_id}")
            lines.append(
                f"chunk_position={item.chunk_index + 1}/{item.chunk_count}"
            )
            lines.append(f"source_url={item.source_url}")
            lines.append(f"source_locator={item.source_locator}")
            lines.append(f"freshness_status={item.freshness_status}")
            lines.append(f"source_authority_tier={item.source_authority_tier}")
            if item.cycle_label:
                lines.append(f"cycle_label={item.cycle_label}")
            contextual_summary = _extract_contextual_summary(item)
            if contextual_summary:
                lines.append(
                    "[document context from contextual retrieval — "
                    "do NOT cite this directly, use only for comprehension]"
                )
                lines.append(contextual_summary)
            lines.append("content:")
            lines.append(item.content)
            context_window = getattr(item, "context_window", "")
            if context_window and not strip_context_window:
                lines.append("[surrounding context from adjacent chunks — "
                             "do NOT cite this directly, use only for comprehension]")
                lines.append(context_window)
            lines.append("")
    lines.extend(
        [
            "JSON response schema:",
            '{',
            '  "status": "answered|abstained",',
            '  "answer_text": "string",',
            '  "claims": [{"text": "string", "citation_ids": ["[1]"]}],',
            '  "warnings": ["string"]',
            '}',
        ]
    )
    return "\n".join(lines)


def _extract_contextual_summary(item: "RetrievedEvidence") -> str:
    contextualized_text = getattr(item, "contextualized_text", "")
    content = getattr(item, "content", "")
    if not contextualized_text or contextualized_text == content:
        return ""
    if content and contextualized_text.endswith(content):
        prefix = contextualized_text[:-len(content)].strip()
        if prefix:
            return prefix
        return ""
    return contextualized_text.strip()
