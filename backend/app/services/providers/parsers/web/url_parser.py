"""URL Parser — delegates to HTML parser."""
from app.services.providers.parsers.web.html_parser import parse as parse_html

def parse(loaded_data):
    return parse_html(loaded_data)