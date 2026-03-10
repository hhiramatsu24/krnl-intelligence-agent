"""
Intelligence briefing: collects data from three monitors, deep-reads top Reddit
and HN links with two parallel Kernel browsers, and produces a structured weekly
briefing via Claude.
"""
import asyncio
import os
import re
import sys
from datetime import date
from io import StringIO
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from kernel import Kernel
from playwright.async_api import async_playwright

load_dotenv()


from reddit_monitor_nk import main as reddit_main
from hn_monitor import main as hn_main
from browserbase_tracker import main as browserbase_main


def extract_urls(text: str, max_urls: int) -> list[str]:
    """Extract unique Reddit and HN URLs from text, skip report/txt links."""
    patterns = [
        r"https://www\.reddit\.com/r/[^\s]+",
        r"https://news\.ycombinator\.com/item[^\s]+",
    ]
    seen: set[str] = set()
    urls: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text):
            url = m.group(0).rstrip(".,;:)]}>\"'")
            if "report" in url.lower() or ".txt" in url.lower():
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
                if len(urls) >= max_urls:
                    return urls
    return urls


async def read_page(page, url: str) -> str:
    """Navigate to URL, wait for render, extract body text. Return header + first 2000 chars."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        content = await page.evaluate("() => (document.body?.innerText || '').trim()")
        content = content[:2000]
        return f"=== {url} ===\n{content}"
    except Exception as e:
        return f"=== {url} ===\n(Error: {e})"


async def read_links_with_kernel(urls: list[str], label: str) -> str:
    """Create Kernel browser, visit each URL sequentially, collect content."""
    api_key = os.environ.get("KERNEL_API_KEY")
    if not api_key:
        return f"{label}\n(Error: KERNEL_API_KEY not set)"
    kernel = Kernel(api_key=api_key)
    kernel_browser = kernel.browsers.create(stealth=True)
    parts = [label]
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
                for i, url in enumerate(urls):
                    content = await read_page(page, url)
                    parts.append(content)
                    if i < len(urls) - 1:
                        await asyncio.sleep(2)
            finally:
                await browser.close()
                kernel.browsers.delete_by_id(kernel_browser.session_id)
    except Exception as e:
        parts.append(f"(Error: {e})")
    return "\n\n".join(parts)


async def deep_read_all_links(
    reddit_urls: list[str], hn_urls: list[str]
) -> tuple[str, str]:
    """Run two Kernel browsers in parallel to deep-read Reddit and HN links."""
    reddit_content, hn_content = await asyncio.gather(
        read_links_with_kernel(reddit_urls, "REDDIT DEEP READ"),
        read_links_with_kernel(hn_urls, "HN DEEP READ"),
    )
    return reddit_content, hn_content


async def main() -> None:
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)

    # STEP 1: Capture output from all three monitors
    print("Step 1: Collecting data...")
    buffer = StringIO()
    old = sys.stdout
    sys.stdout = buffer
    try:
        reddit_main()
    finally:
        sys.stdout = old
    reddit_output = buffer.getvalue()

    buffer = StringIO()
    old = sys.stdout
    sys.stdout = buffer
    try:
        await hn_main()
    finally:
        sys.stdout = old
    hn_output = buffer.getvalue()

    buffer = StringIO()
    old = sys.stdout
    sys.stdout = buffer
    try:
        await browserbase_main()
    finally:
        sys.stdout = old
    browserbase_output = buffer.getvalue()

    (reports_dir / f"reddit_report_{date.today()}.txt").write_text(
        reddit_output, encoding="utf-8"
    )
    (reports_dir / f"hn_report_{date.today()}.txt").write_text(
        hn_output, encoding="utf-8"
    )
    (reports_dir / f"browserbase_report_{date.today()}.txt").write_text(
        browserbase_output, encoding="utf-8"
    )

    # STEP 2: Extract URLs for deep read
    reddit_urls = extract_urls(reddit_output, max_urls=5)
    hn_urls = extract_urls(hn_output, max_urls=5)

    # STEP 3: Deep read links with two parallel Kernel browsers
    print("Step 2: Deep reading links with 2 parallel Kernel browsers...")
    reddit_deep, hn_deep = await deep_read_all_links(reddit_urls, hn_urls)

    # STEP 4: Call Claude API
    print("Step 3: Generating briefing with Claude...")
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        user_message = f"""Here is this week's intelligence data including full content from the top Reddit posts and HN threads. Produce a briefing with these sections:

1. EXECUTIVE SUMMARY (3-4 sentences): The single most important thing Kernel learned this week and why it matters.

2. BROWSERBASE PAIN SIGNALS: Top 3 posts where developers express frustration with Browserbase or seek alternatives. For each include the URL, a one-sentence summary of the complaint, and why it is a sales opportunity for Kernel.

3. COMPETITIVE INTELLIGENCE: What changed on Browserbase's website. Cover pricing vs Kernel, recent features, and what the hiring pattern signals about their roadmap.

4. RECOMMENDED ACTIONS: 2-3 specific actions for Kernel's team this week. Not vague — specific like 'reply to [URL] mentioning Kernel's [feature]' or 'update pricing page to show Kernel is 2x cheaper at developer tier'.

--- REDDIT SUMMARY ---
{reddit_output[:2000]}

--- HN SUMMARY ---
{hn_output[:1500]}

--- BROWSERBASE TRACKER ---
{browserbase_output[:2500]}

--- REDDIT DEEP READ (full post content) ---
{reddit_deep[:3000]}

--- HN DEEP READ (full thread content) ---
{hn_deep[:3000]}
"""
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system="You are an intelligence analyst for Kernel, a browser infrastructure startup that competes directly with Browserbase. You receive weekly data from three sources plus deep-read content from the most relevant posts and threads. Produce a concise, actionable briefing for Kernel's team. Be direct and specific. Prioritize signals that indicate sales opportunities or competitive threats. Avoid generic observations.",
            messages=[{"role": "user", "content": user_message}],
        )
        briefing = ""
        for block in message.content:
            text = getattr(block, "text", None)
            if text:
                briefing = text
                break
    except Exception as e:
        print(f"Error calling Anthropic API: {e}")
        return

    # STEP 5: Output and save
    header = f"""
KERNEL INTELLIGENCE AGENT
Weekly Briefing — {date.today()}
Generated by: intelligence_briefing.py
{"="*50}

"""
    footer = f"""

{"="*50}
End of briefing. Next run recommended in 7 days.
Raw data files saved to: reports/
"""
    full_report = header + briefing + footer

    print(briefing)
    path = reports_dir / f"intelligence_briefing_{date.today()}.txt"
    path.write_text(full_report, encoding="utf-8")
    print("\n" + "=" * 50)
    print(f"Briefing saved to: {path}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
