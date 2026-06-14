"""
Web Loaders — HTML files and URL scraping.
"""
from app.services.providers.loaders.web.html_loader import load as load_html
from app.services.providers.loaders.web.url_loader import load as load_url

__all__ = ["load_html", "load_url"]
