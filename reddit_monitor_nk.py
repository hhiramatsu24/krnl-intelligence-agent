"""
Reddit monitor: searches Reddit for Browserbase mentions using Reddit's JSON API.
No browser needed — Reddit exposes search results as clean JSON.
"""
import time
import os
import requests
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SEARCH_QUERIES = [
    "Browserbase",
    "Browserbase alternative",
    "Browserbase problem",
]

HEADERS = {
    "User-Agent": "KernelIntelAgent/1.0 (research project; contact: hhiramatsu24@g.ucla.edu)"
}

TOP_POSTS_PER_SEARCH = 10


def search_reddit(query: str) -> list[dict]:
    """Search Reddit using the JSON API and return a list of posts."""
    url = "https://www.reddit.com/search.json"
    params = {
        "q": query,
        "sort": "new",
        "t": "month",
        "limit": TOP_POSTS_PER_SEARCH,
    }
    response = requests.get(url, headers=HEADERS, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    posts = []
    for child in data["data"]["children"]:
        post = child["data"]
        posts.append({
            "title": post.get("title", "No title"),
            "url": "https://www.reddit.com" + post.get("permalink", ""),
            "subreddit": "r/" + post.get("subreddit", "unknown"),
            "score": post.get("score", 0),
            "num_comments": post.get("num_comments", 0),
            "selftext": post.get("selftext", "")[:300],
        })
    return posts


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
        lines.append(f"   Subreddit: {post['subreddit']}")
        lines.append(f"   Score: {post['score']}  |  Comments: {post['num_comments']}")
        if post['selftext']:
            lines.append(f"   Preview: {post['selftext'][:200]}...")
        lines.append("")
    return "\n".join(lines).strip()


def main() -> None:
    all_posts = []
    seen_urls = set()

    for i, query in enumerate(SEARCH_QUERIES):
        print(f"Searching Reddit for: '{query}'...")
        try:
            posts = search_reddit(query)
            for post in posts:
                if post["url"] not in seen_urls:
                    seen_urls.add(post["url"])
                    all_posts.append(post)
        except Exception as e:
            print(f"Warning: failed to search for '{query}': {e}")

        if i < len(SEARCH_QUERIES) - 1:
            time.sleep(2)

    report = format_report(all_posts)
    print("\n" + report)

    report_path = Path(__file__).parent / f"reddit_report_{date.today()}.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
