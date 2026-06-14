"""
ParsedDocument — the structured contract between Parser and Chunking Engine.
"""
from dataclasses import dataclass, field
from typing import Optional, Any
import json


@dataclass
class Section:
    heading: str
    content: str
    level: int = 1
    page: int = 1
    font_size: Optional[float] = None


@dataclass
class Table:
    content: str
    headers: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0
    page: int = 1


@dataclass
class Image:
    caption: str = ""                # "System architecture diagram"
    ocr_text: str = ""               # text detected inside the image
    image_path: str = ""             # "/uploads/images/doc123_page3_1.png"
    page: int = 1
    bbox: list[float] = field(default_factory=list)  # [x0, y0, x1, y1]

    @property
    def text_for_embedding(self) -> str:
        """Combined text used for chunking/embedding."""
        parts = []
        if self.caption:
            parts.append(self.caption)
        if self.ocr_text:
            parts.append(self.ocr_text)
        return " — ".join(parts) if parts else ""


@dataclass
class ParsedDocument:
    title: str = ""
    sections: list[Section] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    images: list[Image] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    num_pages: int = 1
    file_type: str = ""
    category: str = "document"
    ocr_quality: str = "good"
    ocr_issues: list[str] = field(default_factory=list)

    @property
    def total_sections(self):
        return len(self.sections)

    @property
    def total_tables(self):
        return len(self.tables)

    @property
    def total_images(self):
        return len(self.images)

    @property
    def total_chars(self):
        chars = sum(len(s.content) + len(s.heading) for s in self.sections)
        chars += sum(len(t.content) for t in self.tables)
        chars += sum(len(i.text_for_embedding) for i in self.images)
        return chars

    def to_dict(self):
        return {
            "title": self.title,
            "sections": [
                {"heading": s.heading, "content": s.content, "level": s.level,
                 "page": s.page, "font_size": s.font_size}
                for s in self.sections
            ],
            "tables": [
                {"content": t.content, "headers": t.headers, "rows": t.rows,
                 "num_rows": t.num_rows, "num_cols": t.num_cols, "page": t.page}
                for t in self.tables
            ],
            "images": [
                {"caption": i.caption, "ocr_text": i.ocr_text,
                 "image_path": i.image_path, "page": i.page, "bbox": i.bbox,
                 "text_for_embedding": i.text_for_embedding}
                for i in self.images
            ],
            "metadata": self.metadata,
            "num_pages": self.num_pages,
            "file_type": self.file_type,
            "category": self.category,
            "ocr_quality": self.ocr_quality,
            "ocr_issues": self.ocr_issues,
            "total_sections": self.total_sections,
            "total_tables": self.total_tables,
            "total_images": self.total_images,
            "total_chars": self.total_chars,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d):
        sections = [Section(**s) for s in d.get("sections", [])]
        tables = [Table(**t) for t in d.get("tables", [])]
        images = []
        for img in d.get("images", []):
            images.append(Image(
                caption=img.get("caption", ""),
                ocr_text=img.get("ocr_text", ""),
                image_path=img.get("image_path", ""),
                page=img.get("page", 1),
                bbox=img.get("bbox", []),
            ))
        return cls(
            title=d.get("title", ""),
            sections=sections, tables=tables, images=images,
            metadata=d.get("metadata", {}),
            num_pages=d.get("num_pages", 1),
            file_type=d.get("file_type", ""),
            category=d.get("category", "document"),
            ocr_quality=d.get("ocr_quality", "good"),
            ocr_issues=d.get("ocr_issues", []),
        )

    def to_content_blocks(self):
        """Convert to [{type, content, page}] for the chunking engine."""
        blocks = []

        for section in self.sections:
            content = section.content
            if section.heading:
                content = f"[Section: {section.heading}]\n{content}"
            blocks.append({"type": "text", "content": content, "page": section.page})

        for table in self.tables:
            blocks.append({"type": "table", "content": table.content, "page": table.page})

        # Images: embed their text description so LLM can find them
        for image in self.images:
            text = image.text_for_embedding
            if text:
                content = f"[Image: {text}]"
                if image.image_path:
                    content += f"\n[image_path: {image.image_path}]"
                blocks.append({"type": "image", "content": content, "page": image.page})

        blocks.sort(key=lambda b: b["page"])
        return blocks