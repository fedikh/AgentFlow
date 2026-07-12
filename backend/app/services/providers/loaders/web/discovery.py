"""
Web URL discovery — turns a website / sitemap / RSS feed into a list of URLs
to ingest. Content fetching happens afterwards (per-URL, via the web loader).

  crawl_website(url)  → same-domain BFS with depth + page limits + dedup
  discover_sitemap(url) → parse <loc> entries (follows sitemap indexes)
  discover_rss(url)   → feedparser → article links
"""
import logging
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

_UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")}

_SKIP_EXT = (".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
             ".css", ".js", ".ico", ".mp4", ".mp3", ".woff", ".woff2", ".ttf",
             ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rss", ".atom")


def _skip(url: str) -> bool:
    return urlparse(url).path.lower().endswith(_SKIP_EXT)


def crawl_website(start_url: str, max_depth: int = 2, max_pages: int = 50,
                  same_domain: bool = True) -> list[str]:
    import requests
    from bs4 import BeautifulSoup
    from collections import deque

    start_url = start_url.rstrip("/")
    domain = urlparse(start_url).netloc
    seen, out = {start_url}, []
    q = deque([(start_url, 0)])

    while q and len(out) < max_pages:
        url, depth = q.popleft()
        try:
            r = requests.get(url, headers=_UA, timeout=15)
            r.raise_for_status()
            if "html" not in r.headers.get("content-type", "").lower():
                continue
        except Exception as e:
            logger.warning(f"[CRAWL] skip {url}: {e}")
            continue

        out.append(url)
        if depth >= max_depth:
            continue
        try:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                link = urljoin(url, a["href"].split("#")[0].strip()).rstrip("/")
                if not link.startswith(("http://", "https://")):
                    continue
                if same_domain and urlparse(link).netloc != domain:
                    continue
                if link in seen or _skip(link):
                    continue
                seen.add(link)
                q.append((link, depth + 1))
                if len(seen) > max_pages * 5:
                    break
        except Exception:
            pass

    return out[:max_pages]


def discover_sitemap(url: str, max_pages: int = 100, _depth: int = 0) -> list[str]:
    import requests
    from lxml import etree

    if _depth > 3:
        return []
    try:
        r = requests.get(url, headers=_UA, timeout=20)
        r.raise_for_status()
        root = etree.fromstring(r.content, etree.XMLParser(recover=True))
    except Exception as e:
        logger.warning(f"[SITEMAP] {url}: {e}")
        return []
    if root is None:
        return []

    is_index = str(root.tag).split("}")[-1] == "sitemapindex"
    locs = [e.text.strip() for e in root.iter()
            if isinstance(e.tag, str) and e.tag.split("}")[-1] == "loc" and e.text]

    urls = []
    for loc in locs:
        if is_index and len(urls) < max_pages:
            urls.extend(discover_sitemap(loc, max_pages - len(urls), _depth + 1))
        elif not _skip(loc):
            urls.append(loc)
        if len(urls) >= max_pages:
            break
    # de-dup preserving order
    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq[:max_pages]


def discover_rss(url: str, max_items: int = 50) -> list[dict]:
    import feedparser
    feed = feedparser.parse(url)
    out = []
    for e in feed.entries[:max_items]:
        link = e.get("link")
        if link:
            out.append({"title": e.get("title", ""), "url": link,
                        "published": e.get("published", "")})
    return out
