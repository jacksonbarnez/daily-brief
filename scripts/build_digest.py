from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import feedparser

LOOKBACK_HOURS = 36
TARGETS = {"business": 5, "technology": 5}
MAX_PER_SOURCE_PER_SECTION = 2

TECH_KEYWORDS = {
    "ai",
    "artificial intelligence",
    "chip",
    "chips",
    "semiconductor",
    "semiconductors",
    "software",
    "cloud",
    "startup",
    "startups",
    "cybersecurity",
    "security",
    "robot",
    "robotics",
    "iphone",
    "android",
    "apple",
    "google",
    "meta",
    "microsoft",
    "amazon",
    "openai",
    "nvidia",
    "tesla",
    "internet",
    "app",
    "apps",
    "data center",
}

BUSINESS_KEYWORDS = {
    "market",
    "markets",
    "earnings",
    "economy",
    "economic",
    "finance",
    "financial",
    "stocks",
    "stock",
    "merger",
    "deal",
    "ipo",
    "bank",
    "banking",
    "inflation",
    "jobs",
    "tariff",
    "company",
    "companies",
    "consumer",
    "retail",
    "oil",
    "fed",
    "revenue",
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "at", "with", "from", "by", "is", "are", "as"
}


@dataclass
class Item:
    title: str
    url: str
    source: str
    published: str
    summary: str
    category: str
    score: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feeds", default="scripts/feeds.json")
    parser.add_argument("--public", default="public")
    parser.add_argument("--out", default="dist")
    return parser.parse_args()


def load_feeds(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_html(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_title(title: str) -> str:
    text = title.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fingerprint(title: str) -> str:
    tokens = [token for token in normalize_title(title).split() if token not in STOPWORDS]
    return " ".join(tokens[:10])


def best_summary(title: str, raw_summary: str) -> str:
    summary = clean_html(raw_summary)
    if not summary:
        return title

    title_norm = normalize_title(title)
    summary_norm = normalize_title(summary)
    if summary_norm.startswith(title_norm):
        summary = summary[len(title):].lstrip(" :-—")

    sentences = re.split(r"(?<=[.!?])\s+", summary)
    chosen = sentences[0].strip() if sentences else summary.strip()
    if len(chosen) < 50 and len(sentences) > 1:
        chosen = f"{chosen} {sentences[1].strip()}".strip()
    if len(chosen) > 220:
        chosen = chosen[:217].rsplit(" ", 1)[0] + "..."
    return chosen or title


def parse_entry_datetime(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        struct_time = getattr(entry, field, None)
        if struct_time:
            return datetime(*struct_time[:6], tzinfo=timezone.utc)

    for field in ("published", "updated", "created"):
        raw_value = getattr(entry, field, None)
        if raw_value:
            try:
                return datetime.fromisoformat(raw_value)
            except Exception:
                continue
    return None


def classify_item(title: str, summary: str, fallback_section: str) -> str:
    haystack = f"{title} {summary}".lower()
    tech_hits = sum(1 for keyword in TECH_KEYWORDS if keyword in haystack)
    business_hits = sum(1 for keyword in BUSINESS_KEYWORDS if keyword in haystack)
    if tech_hits > business_hits:
        return "technology"
    if business_hits > tech_hits:
        return "business"
    return fallback_section


def score_item(published_dt: datetime, source_weight: float, category: str, title: str, summary: str) -> float:
    age_hours = max((datetime.now(timezone.utc) - published_dt).total_seconds() / 3600, 0.1)
    freshness = max(0.0, 1.8 - (age_hours / LOOKBACK_HOURS))
    keyword_bonus = 0.0
    haystack = f"{title} {summary}".lower()
    if category == "technology":
        keyword_bonus += 0.08 * sum(1 for keyword in TECH_KEYWORDS if keyword in haystack)
    if category == "business":
        keyword_bonus += 0.08 * sum(1 for keyword in BUSINESS_KEYWORDS if keyword in haystack)
    return round((freshness * 2.3) + source_weight + min(keyword_bonus, 0.4), 4)


def collect_items(feeds: list[dict]) -> list[Item]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=LOOKBACK_HOURS)
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    items: list[Item] = []

    for feed in feeds:
        parsed = feedparser.parse(feed["url"])
        for entry in parsed.entries:
            published_dt = parse_entry_datetime(entry)
            if not published_dt or published_dt < cutoff:
                continue

            url = getattr(entry, "link", "").strip()
            title = clean_html(getattr(entry, "title", "")).strip()
            summary = best_summary(title, getattr(entry, "summary", "") or getattr(entry, "description", ""))
            if not url or not title:
                continue

            canonical_url = url.split("#", 1)[0]
            title_fingerprint = fingerprint(title)
            if canonical_url in seen_urls or title_fingerprint in seen_titles:
                continue

            category = classify_item(title, summary, feed["section"])
            score = score_item(published_dt, float(feed.get("weight", 1.0)), category, title, summary)

            seen_urls.add(canonical_url)
            seen_titles.add(title_fingerprint)
            items.append(
                Item(
                    title=title,
                    url=canonical_url,
                    source=feed["name"],
                    published=published_dt.isoformat(),
                    summary=summary,
                    category=category,
                    score=score,
                )
            )

    return items


def choose_top_items(items: list[Item]) -> dict[str, list[Item]]:
    sections: dict[str, list[Item]] = {"business": [], "technology": []}
    per_source: dict[str, Counter] = defaultdict(Counter)

    sorted_items = sorted(items, key=lambda item: (item.score, item.published), reverse=True)
    for item in sorted_items:
        section = item.category
        if section not in sections:
            continue
        if len(sections[section]) >= TARGETS[section]:
            continue
        if per_source[section][item.source] >= MAX_PER_SOURCE_PER_SECTION:
            continue
        sections[section].append(item)
        per_source[section][item.source] += 1

    return sections


def render_email(sections: dict[str, list[Item]], generated_at: str) -> dict[str, str]:
    total_items = sum(len(items) for items in sections.values())
    date_label = datetime.fromisoformat(generated_at).astimezone(timezone.utc).strftime("%b %d, %Y")
    subject = f"Daily Brief: {date_label}"

    intro = (
        "Here is your clean daily read on business and technology. "
        f"I picked {total_items} notable stories published in roughly the last {LOOKBACK_HOURS} hours."
    )

    html_parts = [
        "<div style='font-family:Arial,sans-serif;max-width:760px;margin:0 auto;color:#0f172a'>",
        "<h1 style='margin-bottom:6px'>Daily Brief</h1>",
        f"<p style='color:#475569;margin-top:0'>{intro}</p>",
    ]

    text_parts = ["Daily Brief", intro, ""]

    for key, title in (("business", "Business"), ("technology", "Technology")):
        html_parts.append(f"<h2 style='margin-top:28px'>{title}</h2>")
        text_parts.append(title.upper())
        for item in sections[key]:
            domain = urlparse(item.url).netloc.replace("www.", "")
            html_parts.append(
                "<div style='border:1px solid #e2e8f0;border-radius:16px;padding:16px;margin:12px 0'>"
                f"<p style='margin:0 0 8px;color:#64748b;font-size:13px'>{item.source} · {domain}</p>"
                f"<h3 style='margin:0 0 10px;font-size:18px'>{html.escape(item.title)}</h3>"
                f"<p style='margin:0 0 10px;line-height:1.6;color:#334155'>{html.escape(item.summary)}</p>"
                f"<p style='margin:0'><a href='{html.escape(item.url)}'>Open article</a></p>"
                "</div>"
            )
            text_parts.extend(
                [
                    f"- {item.title}",
                    f"  {item.summary}",
                    f"  {item.url}",
                    "",
                ]
            )

    html_parts.append(
        "<p style='margin-top:28px;color:#64748b;font-size:13px'>"
        "Some sources only expose headlines or short excerpts in public feeds. This digest links back to the original articles for full reading."
        "</p></div>"
    )

    notification_lines = []
    for section, title in (("business", "Business"), ("technology", "Technology")):
        if sections[section]:
            top = sections[section][0]
            notification_lines.append(f"{title}: {top.title}")

    return {
        "subject": subject,
        "html": "".join(html_parts),
        "text": "\n".join(text_parts).strip(),
        "notification_title": subject,
        "notification_body": " | ".join(notification_lines)[:280],
    }


def build_digest_payload(sections: dict[str, list[Item]], all_items: list[Item], generated_at: str) -> dict:
    return {
        "generated_at": generated_at,
        "lookback_hours": LOOKBACK_HOURS,
        "stats": {
            "total_items": sum(len(items) for items in sections.values()),
            "total_sources": len({item.source for item in all_items}),
            "raw_feed_items_kept": len(all_items),
        },
        "sections": [
            {
                "id": key,
                "title": key.capitalize(),
                "items": [asdict(item) for item in items],
            }
            for key, items in sections.items()
        ],
    }


def ensure_placeholder_files(out_dir: Path) -> None:
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    placeholder_digest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_hours": LOOKBACK_HOURS,
        "stats": {"total_items": 0, "total_sources": 0, "raw_feed_items_kept": 0},
        "sections": [
            {"id": "business", "title": "Business", "items": []},
            {"id": "technology", "title": "Technology", "items": []},
        ],
    }
    (data_dir / "digest.json").write_text(json.dumps(placeholder_digest, indent=2), encoding="utf-8")
    (data_dir / "mail.json").write_text(
        json.dumps(
            {
                "subject": "Daily Brief",
                "html": "<p>No digest yet.</p>",
                "text": "No digest yet.",
                "notification_title": "Daily Brief",
                "notification_body": "The digest will appear after the first scheduled run.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    feeds_path = Path(args.feeds)
    public_path = Path(args.public)
    out_path = Path(args.out)

    if out_path.exists():
        shutil.rmtree(out_path)
    shutil.copytree(public_path, out_path)

    ensure_placeholder_files(out_path)

    feeds = load_feeds(feeds_path)
    all_items = collect_items(feeds)
    sections = choose_top_items(all_items)
    generated_at = datetime.now(timezone.utc).isoformat()

    digest_payload = build_digest_payload(sections, all_items, generated_at)
    mail_payload = render_email(sections, generated_at)

    data_dir = out_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "digest.json").write_text(json.dumps(digest_payload, indent=2), encoding="utf-8")
    (data_dir / "mail.json").write_text(json.dumps(mail_payload, indent=2), encoding="utf-8")

    print(json.dumps(digest_payload["stats"], indent=2))


if __name__ == "__main__":
    main()
