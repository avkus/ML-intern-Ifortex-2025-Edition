import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def main_test_crawl(test_url):
    browser_conf = BrowserConfig(headless=True)
    run_conf = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    print(f"Testing crawl4ai with URL: {test_url}")
    try:
        async with AsyncWebCrawler(config=browser_conf) as crawler:
            result = await crawler.arun(url=test_url, config=run_conf)
            if result:
                print(f"Crawl4AI Result Object Type: {type(result)}")
                if hasattr(result, 'markdown') and result.markdown:
                    print(f"Extracted Markdown (first 500 chars): {result.markdown[:500]}")
                else:
                    print("No markdown content found in result.")
                if hasattr(result, 'error_message') and result.error_message:
                    print(f"Crawl4AI Error Message: {result.error_message}")
                if hasattr(result, 'status_code') and result.status_code: # Assuming it might have status_code
                    print(f"Crawl4AI Status Code: {result.status_code}")
            else:
                print("Crawl4AI returned a None result.")
    except Exception as e:
        print(f"Exception during isolated crawl4ai test: {e}")

if __name__ == "__main__":
    # Test with Wikipedia
    asyncio.run(main_test_crawl("https://ru.wikipedia.org/wiki/%D0%97%D0%B0%D0%B3%D0%BB%D0%B0%D0%B2%D0%BD%D0%B0%D1%8F_%D1%81%D1%82%D1%80%D0%B0%D0%BD%D0%B8%D1%86%D0%B0"))
    # Test with GitHub
    # asyncio.run(main_test_crawl("https://github.com/avkus/ML-intern-Ifortex-2025-Edition"))