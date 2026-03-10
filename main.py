"""
Standalone script: visits a URL and returns the page title
using the Kernel Python SDK and Playwright.
"""
import asyncio
import os
from dotenv import load_dotenv
from kernel import Kernel
from playwright.async_api import async_playwright

load_dotenv()

async def get_page_title(url: str) -> str:
    kernel = Kernel(api_key=os.getenv("KERNEL_API_KEY"))
    kernel_browser = kernel.browsers.create()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(
            kernel_browser.cdp_ws_url
        )
        try:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(url)
            return await page.title()
        finally:
            await browser.close()
            kernel.browsers.delete_by_id(kernel_browser.session_id)

if __name__ == "__main__":
    title = asyncio.run(get_page_title("https://www.google.com"))
    print(f"Page title: {title}")