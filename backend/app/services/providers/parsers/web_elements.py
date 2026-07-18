"""
Canonical web element builder (HTML → element schema) with BeautifulSoup.

Normalizes an HTML page into the same envelope every other parser uses:

    heading (h1-h6) · paragraph · list_item · table · code · image · quote

Plus document-level collections returned separately: images, links, and page
metadata (title, description, language, author, published/modified, canonical).

The *fetcher* (Crawl4AI / requests) is separate — this only turns HTML into the
Canonical Document Model, so it works for URL, HTML file, and raw HTML alike.
"""
import re
from urllib.parse import urljoin, urlparse

_NOISE = {"script", "style", "nav", "footer", "aside", "header", "noscript",
          "form", "iframe", "svg", "button"}
_HEADING = re.compile(r"^h([1-6])$")


def _meta(soup, name=None, prop=None):
    if name:
        t = soup.find("meta", attrs={"name": name})
        if t and t.get("content"):
            return t["content"].strip()
    if prop:
        t = soup.find("meta", attrs={"property": prop})
        if t and t.get("content"):
            return t["content"].strip()
    return None


def extract_web_metadata(soup, base_url=None):
    title = (_meta(soup, prop="og:title")
             or (soup.title.get_text(strip=True) if soup.title else None))
    canonical = None
    lc = soup.find("link", attrs={"rel": "canonical"})
    if lc and lc.get("href"):
        canonical = lc["href"].strip()
    canonical = canonical or _meta(soup, prop="og:url") or base_url
    html_tag = soup.find("html")
    lang = (html_tag.get("lang") if html_tag else None) or _meta(soup, name="language")
    domain = urlparse(canonical or base_url or "").netloc or None
    return {
        "title": title,
        "description": _meta(soup, name="description") or _meta(soup, prop="og:description"),
        "language": (lang or "").split("-")[0] or None,
        "author": _meta(soup, name="author") or _meta(soup, prop="article:author"),
        "published_at": _meta(soup, prop="article:published_time") or _meta(soup, name="date"),
        "modified_at": _meta(soup, prop="article:modified_time"),
        "canonical_url": canonical,
        "domain": domain,
    }


def _code_lang(node):
    for el in (node, node.find("code")):
        if not el:
            continue
        for cls in (el.get("class") or []):
            if cls.startswith(("language-", "lang-")):
                return cls.split("-", 1)[1]
    return ""


def _srcset_best(v):
    """Largest candidate from a srcset ('u1 320w, u2 640w' | 'u1 1x, u2 2x')."""
    if not v:
        return ""
    cands = [p.strip().split()[0] for p in v.split(",") if p.strip()]
    return cands[-1] if cands else ""


def _img_src(img):
    """Best REAL image URL — lazy-load aware. Modern pages put the real URL in
    srcset / data-src / data-original while `src` is a 1x1 or data: placeholder.
    Prefer a genuine http(s)/relative URL over any data: placeholder."""
    candidates = [
        img.get("src"), img.get("data-src"), img.get("data-lazy-src"),
        img.get("data-original"), img.get("data-lazy"),
        _srcset_best(img.get("srcset")), _srcset_best(img.get("data-srcset")),
    ]
    real = [c.strip() for c in candidates if c and c.strip()]
    for c in real:
        if not c.lower().startswith("data:"):
            return c
    return ""


def _img_is_tiny(img):
    """True if width/height attributes mark this as an icon/tracking pixel."""
    for attr in ("width", "height"):
        v = img.get(attr)
        try:
            if v and int(str(v).lower().replace("px", "").strip()) <= 32:
                return True
        except (ValueError, TypeError):
            pass
    return False


def build_web_elements(html, base_url=None):
    """Return (elements, images, links, metadata, text_repr)."""
    from bs4 import BeautifulSoup
    from app.services.providers.parsers.parsed_document import Image

    soup = BeautifulSoup(html, "html.parser")
    meta = extract_web_metadata(soup, base_url)

    root = soup.find("article") or soup.find("main") or soup.body or soup
    for tag in root.find_all(_NOISE):
        tag.decompose()

    elements, images, links, text_lines = [], [], [], []
    seen_links = set()
    seen_srcs = set()
    ro = {"n": 0}

    def emit(etype, content, level=None, list_level=None):
        ro["n"] += 1
        el = {
            "id": f"e{ro['n']}", "type": etype, "content": content,
            "location": {"page": 1, "bbox": []},
            "hierarchy": {"parent": None, "parent_section": None},
            "metadata": {"reading_order": ro["n"]},
        }
        if level is not None:
            el["level"] = level
        if list_level:
            el["metadata"]["list_level"] = list_level
        elements.append(el)

    def collect_links(node):
        for a in node.find_all("a", href=True):
            href = urljoin(base_url or "", a["href"].strip())
            text = a.get_text(" ", strip=True)
            key = (text, href)
            if href.startswith(("http://", "https://")) and key not in seen_links:
                seen_links.add(key)
                links.append({"text": text, "url": href})

    def emit_image(img, caption=""):
        src = _img_src(img)                 # lazy-load aware (srcset/data-src/…)
        if not src or _img_is_tiny(img):    # skip placeholders / icons / pixels
            return
        src = urljoin(base_url or "", src)
        if src in seen_srcs:                 # already emitted (inline pass)
            return
        seen_srcs.add(src)
        alt = (img.get("alt") or "").strip()
        cap = (caption or alt or "").strip()
        emit("image", {"src": src, "alt": alt, "caption": cap,
                       "text_for_embedding": cap})
        images.append(Image(caption=cap or "Image", ocr_text="", image_path=src,
                            page=1, bbox=[], text_for_embedding=cap))
        if cap:
            text_lines.append(cap)

    def emit_table(table):
        headers = []
        head = table.find("thead")
        if head:
            headers = [th.get_text(" ", strip=True) for th in head.find_all(["th", "td"])]
        body_rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")
        if not headers and body_rows:
            first = body_rows[0]
            if first.find("th"):
                headers = [c.get_text(" ", strip=True) for c in first.find_all(["th", "td"])]
                body_rows = body_rows[1:]
        rows = []
        for tr in body_rows:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if not cells:
                continue
            if not headers:
                headers = [f"col{i+1}" for i in range(len(cells))]
            rows.append({headers[i] if i < len(headers) else f"col{i+1}": v
                         for i, v in enumerate(cells)})
        if not headers and not rows:
            return
        md = [" | ".join(headers), " | ".join("---" for _ in headers)]
        md += [" | ".join(str(r.get(h, "")) for h in headers) for r in rows]
        emit("table", {"caption": "", "headers": headers, "rows": rows, "markdown": "\n".join(md)})
        text_lines.append("\n".join(md))

    def emit_inner_images(node):
        """Emit images nested inside a text block (p / li / table / quote) at
        their position, so images keep their reading order instead of being
        appended at the end."""
        for im in node.find_all("img"):
            emit_image(im)

    def emit_list(lst, depth):
        for li in lst.find_all("li", recursive=False):
            nested = li.find_all(["ul", "ol"], recursive=False)
            for n in nested:
                n.extract()
            text = li.get_text(" ", strip=True)
            collect_links(li)
            if text:
                emit("list_item", {"text": text}, list_level=depth)
                text_lines.append(text)
            emit_inner_images(li)
            for n in nested:
                emit_list(n, depth + 1)

    def walk(node):
        for child in node.children:
            name = getattr(child, "name", None)
            if not name:
                continue
            name = name.lower()
            if name in _NOISE:
                continue
            mh = _HEADING.match(name)
            if mh:
                t = child.get_text(" ", strip=True)
                if t:
                    emit("heading", {"text": t}, level=int(mh.group(1)))
                    text_lines.append(t)
            elif name == "p":
                collect_links(child)
                t = child.get_text(" ", strip=True)
                if t:
                    emit("paragraph", {"text": t})
                    text_lines.append(t)
                emit_inner_images(child)      # images inside <p>, in place
            elif name in ("ul", "ol"):
                emit_list(child, 1)
            elif name == "table":
                emit_table(child)
                emit_inner_images(child)      # images inside table cells, in place
            elif name == "pre":
                # NO separator: a "\n" separator inserts a newline between EVERY
                # text node, which shreds syntax-highlighted code (each token is
                # a <span>). Empty separator preserves the source's own whitespace.
                for br in child.find_all("br"):
                    br.replace_with("\n")
                code = child.get_text().rstrip()
                if code.strip():
                    emit("code", {"text": code, "language": _code_lang(child)})
                    text_lines.append(code)
            elif name == "blockquote":
                t = child.get_text(" ", strip=True)
                if t:
                    emit("quote", {"text": t})
                    text_lines.append(t)
                emit_inner_images(child)
            elif name == "img":
                emit_image(child)
            elif name == "figure":
                img = child.find("img")
                cap = child.find("figcaption")
                if img:
                    emit_image(img, caption=cap.get_text(" ", strip=True) if cap else "")
            else:
                walk(child)   # recurse into containers (div/section/span/…)

    walk(root)

    # Safety net: catch any image the structural walk still missed (unusual
    # nesting). Dedup by src keeps everything already emitted inline at its
    # correct reading-order position; only genuinely-missed images append here.
    for im in root.find_all("img"):
        emit_image(im)

    return elements, images, links, meta, "\n\n".join(text_lines)
