from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

@app.post("/scrape/")
async def scrape_url(request_data: ScrapeRequest):
    target_url = request_data.url
    browser_conf = BrowserConfig(headless=True)
    run_conf = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    try:
        async with AsyncWebCrawler(config=browser_conf) as crawler:
            result = await crawler.arun(url=target_url, config=run_conf)
        if result and hasattr(result, 'markdown') and result.markdown:
            return {"status": "success", "extracted_markdown": result.markdown.strip()}
        elif result and hasattr(result, 'error_message') and result.error_message:
            raise HTTPException(status_code=500, detail=f"Crawl4AI error: {result.error_message}")
        else:
            raise HTTPException(status_code=500, detail="Crawl4AI returned unexpected result or no content.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error during crawl: {str(e)}") 