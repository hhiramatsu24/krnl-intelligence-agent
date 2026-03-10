"""
Browserbase competitive intelligence tracker.
Uses a Kernel cloud browser to visit Browserbase's website and extract key data.
"""
import asyncio
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from kernel import Kernel
from playwright.async_api import async_playwright

load_dotenv()

PAGE_WAIT_MS = 4000
DELAY_BETWEEN_PAGES = 2
MAX_CONTENT_CHARS = 1500


async def extract_pricing(page) -> str:
    """Extract pricing content from browserbase.com/pricing."""
    try:
        await page.goto("https://www.browserbase.com/pricing", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(PAGE_WAIT_MS)
        content = await page.evaluate(
            """
            () => {
                const body = document.body;
                if (!body) return '';
                const text = body.innerText || body.textContent || '';
                return text.trim();
            }
            """
        )
        content = content or "(Failed to extract)"
        marker = "Power your automations"
        if marker in content:
            content = content[content.find(marker):]
        return content
    except Exception as e:
        return f"(Error: {e})"


async def extract_changelog(page) -> str:
    """Extract recent changelog entries from browserbase.com/changelog."""
    try:
        await page.goto("https://www.browserbase.com/changelog", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(PAGE_WAIT_MS)
        content = await page.evaluate(
            """
            () => {
                const body = document.body;
                if (!body) return '';
                const text = body.innerText || body.textContent || '';
                return text.trim();
            }
            """
        )
        content = content or "(Failed to extract)"
        marker = "Browserbase Changelog"
        if marker in content:
            content = content[content.find(marker):]
        return content
    except Exception as e:
        return f"(Error: {e})"


async def extract_careers(page) -> list[str]:
    """Extract job listings from browserbase.com/careers."""
    try:
        await page.goto("https://www.browserbase.com/careers", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(PAGE_WAIT_MS)
        raw_text = await page.evaluate("() => document.body.innerText")
        
        # Known job titles from the careers page — extract by finding lines
        # that appear before "EngineeringSan Francisco" or "GTMSan Francisco"
        DEPARTMENTS = {"Engineering", "GTM", "Design", "Product", "Operations"}
        SKIP_LINES = {
            "Apply", "San Francisco", "Full-time", "Remote", "Part-time",
            "Careers", "Open Roles", "Join us", "View all", "Get a Demo",
            "Log in", "Sign Up", "Products", "Solutions", "Resources",
            "Pricing", "Docs", "Customers", "Enterprise", "Templates","Get Started",
        }
        
        jobs = []
        seen = set()
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
        
        for line in lines:
            # Skip nav/footer noise
            if line in SKIP_LINES:
                continue
            # Skip department names
            if line in DEPARTMENTS:
                continue
            # Skip very short or very long lines
            if len(line) < 8 or len(line) > 60:
                continue
            # Skip lines that are clearly not job titles
            if any(x in line for x in ["$", "http", "©", "Follow", "Read more", "→"]):
                continue
            # A job title line is typically followed by a department line
            idx = lines.index(line)
            if idx + 1 < len(lines) and lines[idx + 1] in DEPARTMENTS:
                if line not in seen:
                    seen.add(line)
                    jobs.append(line)
        
        return jobs if jobs else ["(No job listings found — page structure may have changed)"]
    except Exception as e:
        return [f"(Error: {e})"]


def format_report(pricing_content: str, changelog_content: str, jobs_list: list[str]) -> str:
    """Build the formatted report string."""
    lines = [
        "BROWSERBASE COMPETITIVE INTELLIGENCE REPORT",
        f"Date: {date.today()}",
        "",
        "=" * 60,
        "PRICING",
        "=" * 60,
        (pricing_content[:MAX_CONTENT_CHARS] + "..." if len(pricing_content) > MAX_CONTENT_CHARS else pricing_content),
        "",
        "=" * 60,
        "RECENT CHANGELOG",
        "=" * 60,
        (changelog_content[:MAX_CONTENT_CHARS] + "..." if len(changelog_content) > MAX_CONTENT_CHARS else changelog_content),
        "",
        "=" * 60,
        "OPEN ROLES",
        "=" * 60,
    ]
    for i, job in enumerate(jobs_list, 1):
        lines.append(f"{i}. {job}")
    lines.append("")
    lines.append("End of report. Run weekly for change detection.")
    return "\n".join(lines)


async def main() -> None:
    api_key = os.environ.get("KERNEL_API_KEY")
    if not api_key:
        raise RuntimeError("KERNEL_API_KEY environment variable is required")

    kernel = Kernel(api_key=api_key)
    kernel_browser = kernel.browsers.create(stealth=True)

    pricing_content = "(Not scraped)"
    changelog_content = "(Not scraped)"
    jobs_list: list[str] = []

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(
                kernel_browser.cdp_ws_url
            )
            try:
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()

                pricing_content = await extract_pricing(page)
                await asyncio.sleep(DELAY_BETWEEN_PAGES)

                changelog_content = await extract_changelog(page)
                await asyncio.sleep(DELAY_BETWEEN_PAGES)

                jobs_list = await extract_careers(page)

            finally:
                await browser.close()
                kernel.browsers.delete_by_id(kernel_browser.session_id)

    except Exception as e:
        print(f"Error: {e}")
        raise

    report = format_report(pricing_content, changelog_content, jobs_list)
    print(report)

    report_path = Path(__file__).parent / f"browserbase_report_{date.today()}.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
