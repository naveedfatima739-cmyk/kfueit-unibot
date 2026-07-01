from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from unibot.crawl.fetchers import FetchedArtifact, RawArtifactFetcher
from unibot.crawl.jobs import CrawlJob
from unibot.db.repositories.source_registry import (
    CrawlMethod,
    SourceRegistryEntry,
    _build_entry,
)
from unibot.domain.source_policies import get_source_policy
from unibot.domain.types import ContentKind, PageKind
from unibot.extract.records import ExtractionContext
from unibot.extract.sectionizer import sectionize_html
from unibot.verify.rules import VerificationCandidate


def _fetch_artifact_for_job(
    fetcher: RawArtifactFetcher,
    job: CrawlJob,
) -> FetchedArtifact:
    if job.crawl_method == "wordpress_api":
        return fetcher.fetch_wp_api(job.source_url)
    requires_browser = job.crawl_method == "browser"
    return fetcher.fetch(job.source_url, requires_browser=requires_browser)


def _extract_candidates(
    job: CrawlJob,
    artifact: object,
    source_entries: tuple[SourceRegistryEntry, ...],
) -> tuple[VerificationCandidate, ...]:
    if not isinstance(artifact, FetchedArtifact):
        return ()
    html = artifact.content.decode("utf-8", errors="replace")
    sections = sectionize_html(html=html, source_url=artifact.source_url)
    fetched_at = datetime.now(timezone.utc)
    candidates: list[VerificationCandidate] = []

    for section in sections:
        section_text = section.content
        if not section_text:
            continue
        record_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{job.source_url}#{section.section_id}"))
        record_version_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{record_id}:{fetched_at.isoformat()}",
            )
        )
        conflict_scope_id = f"{job.source_class}:{section.section_label}"
        dedupe_key = hashlib.sha256(section_text.encode()).hexdigest()

        candidates.append(
            VerificationCandidate(
                record_id=record_id,
                record_version_id=record_version_id,
                record_type=job.source_class,
                conflict_scope_id=conflict_scope_id,
                dedupe_key=dedupe_key,
                value_hash=dedupe_key,
                source_authority_tier=job.default_authority_tier,
                source_url=job.source_url,
                source_locator=section.source_locator,
                source_section_id=section.section_id,
                source_section_label=section.section_label,
                cycle_label=job.source_class,
                fetched_at=fetched_at,
                parent_source_url=job.parent_source_url,
                record_payload={
                    "text": section_text[:2000],
                },
            )
        )

    return tuple(candidates)


def _discover_source_entries(
    job: CrawlJob,
    artifact: object,
    exclude_research_subdomains: bool = False,
) -> tuple[SourceRegistryEntry, ...]:
    if not isinstance(artifact, FetchedArtifact):
        return ()
    html = artifact.content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    discovered: list[SourceRegistryEntry] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True)
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        from urllib.parse import urljoin

        absolute_url = urljoin(job.source_url, href)
        if not absolute_url.startswith(("http://", "https://")):
            continue
        policy = get_source_policy(absolute_url)
        if exclude_research_subdomains and policy.source_class == "research_subdomain":
            continue

        page_kind: PageKind
        content_kind: ContentKind
        crawl_method: CrawlMethod = "html_static"

        if policy.source_class == "document_asset":
            page_kind = "official_document"
            content_kind = "official_document"
            crawl_method = "html_static"
        elif policy.source_class == "research_subdomain":
            page_kind = "dedicated_child"
            content_kind = "page_body"
        elif policy.source_class in ("faculty", "program"):
            page_kind = "dedicated_child"
            content_kind = "page_body"
        else:
            page_kind = "overview"
            content_kind = "page_body"

        entry = _build_entry(
            absolute_url,
            source_class=policy.source_class,
            page_kind=page_kind,
            content_kind=content_kind,
            crawl_method=crawl_method,
            refresh_policy="weekly",
            parent_source_url=job.source_url,
            link_text=text or None,
        )
        discovered.append(entry)

    seen = set()
    unique: list[SourceRegistryEntry] = []
    for entry in discovered:
        if entry.source_url not in seen:
            seen.add(entry.source_url)
            unique.append(entry)

    return tuple(unique)


def _build_extraction_context(
    job: CrawlJob,
    artifact: object,
    source_entries: tuple[SourceRegistryEntry, ...],
) -> ExtractionContext:
    if not isinstance(artifact, FetchedArtifact):
        raise TypeError(f"Expected FetchedArtifact, got {type(artifact).__name__}")
    html = artifact.content.decode("utf-8", errors="replace")
    verification_state_by_url: dict[str, str] = {}
    for entry in source_entries:
        verification_state_by_url[entry.source_url] = "eligible"

    return ExtractionContext(
        source_class=job.source_class,
        source_url=artifact.source_url,
        html=html,
        parser_target=job.parser_target,
        default_authority_tier=job.default_authority_tier,
        parent_source_url=job.parent_source_url,
        link_text=job.link_text,
        verification_state_by_url=verification_state_by_url,
        fetch_metadata=artifact.metadata,
    )
