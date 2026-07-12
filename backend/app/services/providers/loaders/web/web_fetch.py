"""
Web fetcher — Crawl4AI primary (JS rendering + markdown), requests fallback.

Returns {html, markdown, metadata, engine}. The HTML is fed to the canonical
web element builder; markdown is a readable preview. Crawl4AI runs in its own
thread/event-loop so it's safe to call from FastAPI's async request context.
"""
import logging

logger = logging.getLogger(__name__)

_UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
}


def _run_async(coro):
    """
    Run a coroutine in a dedicated thread with its own event loop.

    On Windows, Playwright (Crawl4AI's browser) needs asyncio subprocess support,
    which ONLY works on a ProactorEventLoop. uvicorn may install a Selector loop
    policy, so we create a Proactor loop explicitly here. The thread's exception
    is captured (not left to crash the thread with a raw traceback).
    """
    import asyncio
    import sys
    import threading

    box = {}

    def runner():
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            box["v"] = loop.run_until_complete(coro)
        except BaseException as e:      # capture — don't crash the thread
            box["err"] = e
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    t = threading.Thread(target=runner)
    t.start()
    t.join()
    if "err" in box:
        raise box["err"]
    return box.get("v")


def fetch_page(url: str) -> dict:
    try:
        return _fetch_crawl4ai(url)
    except Exception as e:
        logger.warning(f"[WEB] Crawl4AI unavailable/failed ({e}); using requests")
        return _fetch_requests(url)


def _fetch_crawl4ai(url: str) -> dict:
    from crawl4ai import AsyncWebCrawler

    async def run():
        async with AsyncWebCrawler() as crawler:
            return await crawler.arun(url=url)

    res = _run_async(run())
    if res is None or not getattr(res, "success", True):
        raise RuntimeError(getattr(res, "error_message", "crawl failed"))
    html = getattr(res, "html", "") or getattr(res, "cleaned_html", "") or ""
    if not html.strip():
        raise RuntimeError("crawl returned empty html")
    md = ""
    try:
        md = str(getattr(res, "markdown", "") or "")
    except Exception:
        md = ""
    return {"html": html, "markdown": md,
            "metadata": getattr(res, "metadata", None) or {}, "engine": "crawl4ai"}


def _fetch_requests(url: str) -> dict:
    import requests
    r = requests.get(url, headers=_UA, timeout=20)
    r.raise_for_status()
    if not r.text.strip():
        raise ValueError(f"No content found at {url}")
    return {"html": r.text, "markdown": "", "metadata": {}, "engine": "requests"}
