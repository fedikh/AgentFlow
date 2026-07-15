"""Hierarchical parent-child — parent = a section (heading + body), children =
recursive sub-chunks of that parent. Retrieve a precise child, expand with its
parent for context. parent_index links each child to its parent chunk."""
from ..base import (iter_sections, elements_of, is_table, is_image, text_of,
                    page_of, mk_chunk, table_chunk, image_chunk, split_recursive,
                    has_real_image_text)


def chunk(parsed, cfg):
    child_size = cfg.p("child_size", 400)
    mult = cfg.p("parent_multiplier", 4)
    overlap = cfg.p("chunk_overlap", 50)
    parent_size = max(child_size * mult, child_size + 1)

    chunks, idx = [], 0
    for head, body in iter_sections(elements_of(parsed)):
        text_parts, page, standalone = [], None, []
        for el in body:
            if is_table(el):
                standalone.append(("table", el))
            elif is_image(el):
                if has_real_image_text(el):
                    standalone.append(("image", el))
            else:
                t = text_of(el)
                if t:
                    if page is None:
                        page = page_of(el)
                    text_parts.append(t)

        section_text = ((f"{head}\n" if head else "") + "\n".join(text_parts)).strip()
        if section_text:
            parents = (split_recursive(section_text, parent_size, overlap)
                       if len(section_text) > parent_size else [section_text])
            for parent_text in parents:
                parent_idx = idx
                chunks.append(mk_chunk(parent_text, page or 1, idx, "hierarchical",
                                       chunk_level="parent")); idx += 1
                children = split_recursive(parent_text, child_size, overlap)
                if len(children) <= 1:
                    continue                       # parent already child-sized
                for child in children:
                    child = child.strip()
                    if child:
                        chunks.append(mk_chunk(child, page or 1, idx, "hierarchical",
                                               chunk_level="child",
                                               parent_index=parent_idx)); idx += 1

        for kind, el in standalone:
            c = (table_chunk if kind == "table" else image_chunk)(el, idx, "hierarchical", heading=head)
            c["chunk_level"] = "standard"
            chunks.append(c); idx += 1
    return chunks
