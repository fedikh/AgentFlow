"""
PPTX Loader — Docling for text/structure + python-pptx for images (Batch 2).

  * Docling converts the deck to raw text + a ParsedDocument. _docling splits
    one section per slide (page change) so the output is structured, not one
    blob.
  * python-pptx extracts the embedded slide pictures (Docling's default PPTX
    backend doesn't surface them), saving them under uploads/{space_id}/images
    via _docling._get_images_dir so the shared image route can serve them.
  * The real file_path is passed in metadata so image paths land in the served
    folder.

Downstream is unchanged: the shared load-parse step summarizes each image with
Gemini (text_for_embedding) and the DocModal + image route display them — no
PPTX-specific code needed beyond this loader.
"""
import os
import logging

logger = logging.getLogger(__name__)

_converter = None


def _get_converter():
    """
    Create or reuse a Docling converter.

    We intentionally use the DEFAULT converter here. Docling's default PPTX
    pipeline already carries the option object its convert step expects (it
    reads attributes like do_picture_classification), and the MS PowerPoint
    backend extracts embedded images into the document model. Injecting a bare
    custom PipelineOptions breaks convert() with:
        'PipelineOptions' object has no attribute 'do_picture_classification'
    The real image fix is passing the correct file_path in metadata (see load()),
    so _docling saves the extracted images under uploads/{space_id}/images.
    """
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
        logger.info("[PPTX_LOADER] Docling converter created (default pipeline)")
    return _converter


def load(file_path: str) -> dict:
    logger.info(f"[PPTX_LOADER] Loading with Docling: {os.path.basename(file_path)}")

    from app.services.providers.parsers._docling import docling_to_parsed_document

    converter = _get_converter()
    result = converter.convert(file_path)

    # Raw text from markdown export
    raw_text = result.document.export_to_markdown()

    from app.services.providers.loaders._utils import clean_text
    raw_text = clean_text(raw_text)

    # ParsedDocument from structure.
    # NOTE: pass the real file_path so _docling saves images next to it
    # (uploads/{space_id}/images), which the image route can then serve.
    metadata = {
        "source": os.path.basename(file_path),
        "file_path": os.path.abspath(file_path),
        "parser": "docling",
    }
    parsed_doc = docling_to_parsed_document(
        result=result,
        file_type="PPTX",
        category="document",
        metadata=metadata,
    )

    # Docling's default PPTX backend doesn't surface slide pictures, so we
    # extract embedded images directly with python-pptx (reliable) and append
    # them. The shared load-parse step then summarizes each with Gemini.
    try:
        extra_images = _extract_pptx_images(file_path)
        if extra_images:
            parsed_doc.images.extend(extra_images)
            logger.info(f"[PPTX_LOADER] python-pptx extracted {len(extra_images)} image(s)")
    except Exception as e:
        logger.warning(f"[PPTX_LOADER] image extraction skipped: {e}")

    if not raw_text.strip() and not parsed_doc.sections:
        raise ValueError("PPTX contains no readable text")

    num_slides = parsed_doc.num_pages or 1

    logger.info(f"[PPTX_LOADER] {num_slides} slide(s) → "
                f"{parsed_doc.total_sections} sections, "
                f"{parsed_doc.total_tables} tables, "
                f"{parsed_doc.total_images} images")

    return {
        "raw_text": raw_text,
        "num_pages": num_slides,
        "file_type": "PPTX",
        "category": "document",
        "metadata": metadata,
        "total_chars": len(raw_text),
        "parsed_document": parsed_doc.to_dict(),
    }


def _extract_pptx_images(file_path: str) -> list:
    """
    Extract embedded slide images with python-pptx and save them under
    uploads/{space_id}/images (same folder _docling uses), so the shared image
    route can serve them. Returns a list of ParsedDocument Image objects with
    empty text_for_embedding — Gemini fills that in the load-parse step.
    """
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from app.services.providers.parsers.parsed_document import Image
    from app.services.providers.parsers._docling import _get_images_dir

    images_dir = _get_images_dir(os.path.abspath(file_path))
    if not images_dir:
        return []
    os.makedirs(images_dir, exist_ok=True)

    out = []
    counter = {"n": 0}

    def _walk(shape, page):
        # Recurse into grouped shapes
        try:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                for child in shape.shapes:
                    _walk(child, page)
                return
        except Exception:
            pass

        # Any shape that carries an embedded image exposes .image
        try:
            pic = shape.image
        except Exception:
            pic = None
        if pic is None:
            return

        try:
            counter["n"] += 1
            ext = (getattr(pic, "ext", "") or "png").lstrip(".").lower()
            if ext == "jpg":
                ext = "jpeg"
            filename = f"page{page}_img{counter['n']}.{ext}"
            save_path = os.path.join(images_dir, filename)
            with open(save_path, "wb") as f:
                f.write(pic.blob)
            out.append(Image(
                caption="Image",
                ocr_text="",
                image_path=save_path,
                page=page,
                bbox=[],
            ))
        except Exception as e:
            logger.warning(f"[PPTX_LOADER] could not save one image: {e}")

    prs = Presentation(file_path)
    for i, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            _walk(shape, i)

    return out
