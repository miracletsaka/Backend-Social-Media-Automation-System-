from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import tldextract
from bs4 import BeautifulSoup
from readability import Document


HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


@dataclass
class ScrapeResult:
    pages: list[str]
    raw_text: str
    colors: list[str]


def _normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


def _same_site(base_url: str, candidate: str) -> bool:
    a = tldextract.extract(base_url)
    b = tldextract.extract(candidate)
    return (a.domain, a.suffix) == (b.domain, b.suffix)


def _pick_key_pages(base_url: str) -> list[str]:
    # Keep this small to stay fast + reliable
    candidates = [
        "/",
        "/about",
        "/services",
        "/service",
        "/products",
        "/pricing",
        "/contact",
        "/faq",
        "/blog",
    ]

    urls = []
    for path in candidates:
        urls.append(urljoin(base_url, path))

    # de-dupe while preserving order
    out: list[str] = []
    seen = set()
    for u in urls:
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out[:8]


def _extract_readable_text(html: str) -> str:
    # readability gives a cleaner “article body” in many cases
    doc = Document(html)
    cleaned_html = doc.summary(html_partial=True)
    soup = BeautifulSoup(cleaned_html, "lxml")
    text = soup.get_text("\n", strip=True)
    # squash long blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_colors(html: str) -> list[str]:
    colors = set(HEX_RE.findall(html or ""))
    # keep it tidy
    out = list(colors)
    out.sort()
    return out[:20]


async def scrape_brand_site(website_url: str, timeout_s: float = 20.0) -> ScrapeResult:
    base = _normalize_url(website_url)
    if not base:
        raise ValueError("website_url is empty")

    pages = _pick_key_pages(base)

    texts: list[str] = []
    all_colors: set[str] = set()

    headers = {
        "User-Agent": "NeuroflowMarketingBot/1.0 (brand profiling; contact: support@yourdomain.com)"
    }

    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True, headers=headers) as client:
        for url in pages:
            # avoid offsite redirects causing noise
            try:
                r = await client.get(url)
                final_url = str(r.url)
                if not _same_site(base, final_url):
                    continue
                html = r.text or ""
            except Exception:
                continue

            txt = _extract_readable_text(html)
            if txt:
                texts.append(f"URL: {final_url}\n{txt}")

            for c in _extract_colors(html):
                all_colors.add(c)

    raw_text = "\n\n---\n\n".join(texts).strip()
    return ScrapeResult(
        pages=pages,
        raw_text=raw_text[:200000],  # hard cap to avoid giant payloads
        colors=sorted(list(all_colors))[:20],
    )
