"""
Reddit monitor: searches Reddit for posts about Browserbase and returns a clean report.
"""
import asyncio
import os
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from kernel import Kernel
from playwright.async_api import async_playwright

SEARCH_URLS = [
    "https://www.reddit.com/search/?q=Browserbase&sort=new&t=month",
    "https://www.reddit.com/search/?q=Browserbase+alternative&sort=new&t=month",
    "https://www.reddit.com/search/?q=Browserbase+problem&sort=new&t=month",
]
DELAY_BETWEEN_SEARCHES = 2
TOP_POSTS_PER_SEARCH = 10


def format_report(posts: list[dict]) -> str:
    """Format the list of posts into a clean report string."""
    lines = []
    lines.append("BROWSERBASE PAIN SIGNAL REPORT — Reddit")
    lines.append(f"Generated: {date.today()}")
    lines.append(f"Total posts found: {len(posts)}")
    lines.append("=" * 50)
    lines.append("")
    for i, post in enumerate(posts, 1):
        lines.append(f"{i}. {post['title']}")
        lines.append(f"   URL: {post['url']}")
        lines.append(f"   Subreddit: {post['snippet']}")
        lines.append("")
    return "\n".join(lines).strip()


async def scrape_search_results(page, url: str) -> list[dict]:
    """Navigate to a Reddit search URL and scrape top 10 posts."""
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(6000)
    await page.wait_for_selector('a[href*="/comments/"]', timeout=15000)

    posts_data = await page.evaluate(
        """
        (limit) => {
            const posts = [];
            const seen = new Set();
            const links = document.querySelectorAll('a[href*="/comments/"][href*="/r/"]');
            for (const a of links) {
                const href = a.href;
                const match = href.match(/\\/r\\/[^/]+\\/comments\\/[^/]+\\/[^/]+/);
                if (!match) continue;
                const canonical = match[0];
                if (seen.has(canonical)) continue;
                seen.add(canonical);

                let snippet = '';
                const shredditPost = a.closest('shreddit-post');
                const postContainer = shredditPost || a.closest('[data-testid*="post"]') || a.closest('div[data-testid]');
                const container = postContainer || a.closest('faceplate-tracker') || a.parentElement?.parentElement;

                if (container) {
                    const trim = (s) => (s || '').trim().slice(0, 200);
                    const meta = container.querySelector('[class*="search-result-metadata"], [class*="SearchResultMetadata"]');
                    const flair = container.querySelector('[class*="flair"], [slot="flair"], faceplate-tracker[type="flair"]');
                    const desc = container.querySelector('[class*="search-result-description"], [class*="description"], p');
                    const body = container.querySelector('[slot="text-body"], [data-click-id="text"]');

                    if (meta) snippet = trim(meta.textContent);
                    if (!snippet && flair) snippet = trim(flair.textContent);
                    if (!snippet && desc) snippet = trim(desc.textContent);
                    if (!snippet && body) snippet = trim(body.textContent);
                }

                if (!snippet) {
                    const subMatch = href.match(/\\/r\\/([^/]+)/);
                    const flairEl = a.closest('shreddit-post')?.querySelector('[class*="flair"], [slot="flair"]') || a.closest('[data-testid*="post"]')?.querySelector('[class*="flair"]');
                    if (flairEl) snippet = flairEl.textContent?.trim().slice(0, 200) || '';
                    if (!snippet && subMatch) snippet = 'r/' + subMatch[1];
                }

                posts.push({
                    title: a.textContent?.trim() || 'No title',
                    url: href.split('?')[0],
                    snippet: snippet
                });
                if (posts.length >= limit) break;
            }
            return posts;
        }
        """,
        TOP_POSTS_PER_SEARCH,
    )
    return posts_data


async def main() -> None:
    api_key = os.environ.get("KERNEL_API_KEY")
    if not api_key:
        raise RuntimeError("KERNEL_API_KEY environment variable is required")

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

                all_posts: list[dict] = []
                seen_urls: set[str] = set()

                for i, url in enumerate(SEARCH_URLS):
                    try:
                        posts = await scrape_search_results(page, url)
                        for post in posts:
                            if post["url"] not in seen_urls:
                                seen_urls.add(post["url"])
                                all_posts.append(post)
                    except Exception as e:
                        print(f"Warning: failed to scrape {url}: {e}")
                    if i < len(SEARCH_URLS) - 1:
                        await asyncio.sleep(DELAY_BETWEEN_SEARCHES)

                report = format_report(all_posts)
                print(report)

                report_path = Path(__file__).parent / f"reddit_report_{date.today()}.txt"
                report_path.write_text(report, encoding="utf-8")
                print(f"\nReport saved to {report_path}")

            finally:
                await browser.close()
                kernel.browsers.delete_by_id(kernel_browser.session_id)

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())