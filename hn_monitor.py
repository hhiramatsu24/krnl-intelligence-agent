"""
Hacker News monitor: finds Browserbase mentions via Algolia API,
then visits each thread with a Kernel cloud browser for future comment analysis.

Architecture:
- Step 1: HN Algolia API → top 5 threads by points (no browser needed)
- Step 2: Kernel cloud browser visits each thread URL (pages load successfully)
- Step 3 (Phase 5): Claude reads full thread content and extracts key comments
"""
import asyncio
import os
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv
from kernel import Kernel
from playwright.async_api import async_playwright

load_dotenv()

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"
SEARCH_QUERIES = [
    "Browserbase",
    "Browserbase alternative",
    "browser automation",
]
NUMERIC_FILTER = "created_at_i>1700000000"
HITS_PER_PAGE = 10
TOP_THREADS = 5
DELAY_BETWEEN_THREADS = 2
PAGE_WAIT_MS = 3000


def fetch_stories() -> list[dict]:
    """Step 1: Search HN via Algolia API, dedupe, sort by points, return top 5."""
    seen_ids: set[str] = set()
    all_stories: list[dict] = []

    for query in SEARCH_QUERIES:
        try:
            r = requests.get(
                ALGOLIA_URL,
                params={
                    "query": query,
                    "tags": "story",
                    "numericFilters": NUMERIC_FILTER,
                    "hitsPerPage": HITS_PER_PAGE,
                },
                timeout=15,
            )
            r.raise_for_status()
            for hit in r.json().get("hits", []):
                oid = hit.get("objectID")
                if not oid or oid in seen_ids:
                    continue
                seen_ids.add(oid)
                all_stories.append({
                    "objectID": oid,
                    "title": hit.get("title") or "(no title)",
                    "url": hit.get("url") or "",
                    "author": hit.get("author") or "",
                    "points": hit.get("points") or 0,
                    "num_comments": hit.get("num_comments") or 0,
                    "created_at": hit.get("created_at") or "",
                })
        except Exception as e:
            print(f"Warning: Algolia search failed for '{query}': {e}")

    all_stories.sort(key=lambda s: s["points"], reverse=True)
    return all_stories[:TOP_THREADS]


async def visit_thread(page, object_id: str) -> bool:
    """
    Step 2: Visit an HN thread using the Kernel cloud browser.
    Confirms the page loads successfully. Comment extraction handled in Phase 5.
    Returns True if page loaded, False if it failed.
    """
    url = f"https://news.ycombinator.com/item?id={object_id}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(PAGE_WAIT_MS)
        title = await page.title()
        print(f"  Visited thread {object_id} — page title: {title}")
        return True
    except Exception as e:
        print(f"  Failed to visit thread {object_id}: {e}")
        return False


def format_report(threads: list[dict]) -> str:
    """Format threads into a clean report string."""
    lines = [
        "HACKER NEWS — BROWSERBASE MENTIONS",
        f"Generated: {date.today()}",
        f"Total threads: {len(threads)}",
        "=" * 60,
        "",
    ]
    for i, t in enumerate(threads, 1):
        hn_url = f"https://news.ycombinator.com/item?id={t['objectID']}"
        visited = t.get("visited", False)
        lines.append(f"{i}. {t['title']}")
        lines.append(f"   HN URL: {hn_url}")
        if t.get("url"):
            lines.append(f"   Source: {t['url']}")
        lines.append(f"   Points: {t['points']} | Comments: {t['num_comments']} | Author: {t['author']}")
        lines.append(f"   Posted: {t['created_at'][:10]}")
        lines.append(f"   Browser visit: {'✓ confirmed' if visited else '✗ failed'}")
        lines.append(f"   Comment analysis: pending Phase 5 (Claude)")
        lines.append("")
    return "\n".join(lines).strip()


async def main() -> None:
    api_key = os.environ.get("KERNEL_API_KEY")
    if not api_key:
        raise RuntimeError("KERNEL_API_KEY environment variable is required")

    # Step 1: Find top threads via Algolia API
    print("Searching HN via Algolia API...")
    threads = fetch_stories()
    if not threads:
        print("No HN threads found.")
        return
    print(f"Found {len(threads)} threads. Visiting each with Kernel browser...\n")

    # Step 2: Visit each thread with Kernel cloud browser
    kernel = Kernel(api_key=api_key)
    kernel_browser = kernel.browsers.create(stealth=True)

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(
                kernel_browser.cdp_ws_url
            )
            try:
                context = (
                    browser.contexts[0]
                    if browser.contexts
                    else await browser.new_context()
                )
                page = (
                    context.pages[0]
                    if context.pages
                    else await context.new_page()
                )
                for i, thread in enumerate(threads):
                    thread["visited"] = await visit_thread(page, thread["objectID"])
                    if i < len(threads) - 1:
                        await asyncio.sleep(DELAY_BETWEEN_THREADS)
            finally:
                await browser.close()
                kernel.browsers.delete_by_id(kernel_browser.session_id)

    except Exception as e:
        print(f"Browser session error: {e}")
        for thread in threads:
            if "visited" not in thread:
                thread["visited"] = False

    # Step 3: Format and save report
    report = format_report(threads)
    print("\n" + report)

    report_path = Path(__file__).parent / f"hn_report_{date.today()}.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())