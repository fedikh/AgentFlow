"""
Tree-element builders for JSON and XML.

Structured data is a TREE, so these emit tree nodes with the SAME element shape
every other parser uses, so the chunker only ever inspects `content`:

    id, parent_id, type,
    hierarchy     {depth, level},
    location      {path|xpath, line_start, line_end},
    content       {type-specific…},
    metadata      {order, confidence, token_estimate},   ← element-level only
    relationships {parent, children, previous, next}

Document-level metadata (source, source_type, parser, checksum…) lives once on
the ParsedDocument, NOT duplicated on every element.

  JSON: object / array / key_value          (Python `json`)
  XML : xml_element                         (`lxml`)

Builders also return a flat text used for chunking/embedding.
"""
import re


def _tok(v) -> int:
    """Rough token estimate (~4 chars/token)."""
    return max(1, len(str(v)) // 4)


def _link_siblings(child_ids, id_map):
    for i, cid in enumerate(child_ids):
        rel = id_map[cid]["relationships"]
        rel["previous"] = child_ids[i - 1] if i > 0 else None
        rel["next"] = child_ids[i + 1] if i < len(child_ids) - 1 else None


# ══════════════════════════════════════════════════════════════
#  JSON
# ══════════════════════════════════════════════════════════════

def _json_type_name(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, list):
        return "array"
    return "string"


def detect_json_schema(data) -> bool:
    """True if the JSON contains a consistent array-of-objects (tabular schema)."""
    if isinstance(data, list) and len(data) >= 2 and all(isinstance(x, dict) for x in data):
        keys = set(data[0].keys())
        if all(set(x.keys()) == keys for x in data):
            return True
    if isinstance(data, dict):
        return any(detect_json_schema(v) for v in data.values())
    if isinstance(data, list):
        return any(detect_json_schema(v) for v in data)
    return False


def _json_semantic(key, value, is_root):
    jt = _json_type_name(value)
    if jt == "object":
        keys = list(value.keys())
        prims = {k: v for k, v in value.items() if not isinstance(v, (dict, list))}
        if is_root:
            return "Root JSON object with keys: " + ", ".join(keys)
        if prims:
            summary = ", ".join(f"{k}: {v}" for k, v in list(prims.items())[:6])
            return (f"{key}: " if key else "") + summary
        return (f"{key} " if key else "") + f"object with {len(keys)} key" + ("s" if len(keys) != 1 else "")
    if jt == "array":
        n = len(value)
        return (f"{key}: " if key else "") + f"list of {n} item" + ("s" if n != 1 else "")
    if jt == "null":
        return f"{key} is null" if key else "null"
    return f"{key}: {value}" if key else f"{value}"


# JSON element type per json_type (primitive/null get json_key_value / json_null).
_JSON_ELEMENT_TYPE = {
    "object": "json_object",
    "array": "json_array",
    "null": "json_null",
}


def build_json_elements(data, source=None):
    """Return (elements, root_type, schema_detected, text_repr)."""
    elements, id_map, text_lines = [], {}, []
    counter = {"n": 0}
    order = {"n": 0}

    def _new():
        counter["n"] += 1
        return f"json_{counter['n']}"

    def _add(parent_id, path, depth, jt, content, tok):
        order["n"] += 1
        el = {
            "id": _new(), "parent_id": parent_id,
            "type": _JSON_ELEMENT_TYPE.get(jt, "json_key_value"),
            "hierarchy": {"depth": depth, "level": depth},
            "location": {"path": path},
            "content": content,
            "metadata": {"order": order["n"], "confidence": 1.0, "token_estimate": tok},
            "relationships": {"parent": parent_id, "children": [],
                              "previous": None, "next": None},
        }
        elements.append(el)
        id_map[el["id"]] = el
        return el

    def walk(value, path, parent_id, depth, key, cbase=None, is_root=False):
        base = cbase if cbase is not None else path
        jt = _json_type_name(value)
        semantic = _json_semantic(key, value, is_root)

        if jt == "object":
            el = _add(parent_id, path, depth, "object",
                      {"json_type": "object", "key": key, "value": None,
                       "semantic_text": semantic, "keys_count": len(value)}, _tok(semantic))
            ids = [walk(v, f"{base}.{k}", el["id"], depth + 1, k) for k, v in value.items()]
            el["relationships"]["children"] = ids
            _link_siblings(ids, id_map)
            return el["id"]
        if jt == "array":
            el = _add(parent_id, path, depth, "array",
                      {"json_type": "array", "key": key, "value": None,
                       "semantic_text": semantic, "items_count": len(value)}, _tok(semantic))
            ids = [walk(v, f"{base}[{i}]", el["id"], depth + 1, None) for i, v in enumerate(value)]
            el["relationships"]["children"] = ids
            _link_siblings(ids, id_map)
            return el["id"]
        # primitive or null
        _add(parent_id, path, depth, jt,
             {"json_type": jt, "key": key, "value": value, "semantic_text": semantic},
             _tok(value if value is not None else "null"))
        text_lines.append(semantic)
        return elements[-1]["id"]

    # Unwrap a single-key wrapper ({"company": {...}}) at the root: the wrapped
    # value becomes the root element ($), and the wrapper key stays in child paths.
    if isinstance(data, dict) and len(data) == 1:
        root_key = next(iter(data))
        walk(data[root_key], "$", None, 1, None, cbase=f"$.{root_key}", is_root=True)
        root_type = _json_type_name(data[root_key])
    else:
        walk(data, "$", None, 1, None, cbase="$", is_root=True)
        root_type = _json_type_name(data)

    return elements, root_type, detect_json_schema(data), "\n".join(text_lines)


# ══════════════════════════════════════════════════════════════
#  XML  (lxml)
# ══════════════════════════════════════════════════════════════

def _localname(tag):
    if isinstance(tag, str) and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def build_xml_elements(root, source=None):
    """Return (elements, root_name, text_repr). `root` is an lxml Element."""
    from collections import Counter
    from lxml import etree

    elements, id_map, text_lines = [], {}, []
    counter = {"n": 0}
    order = {"n": 0}

    def _new():
        counter["n"] += 1
        return f"xml_{counter['n']}"

    def _namespace(node):
        """{uri, prefix} for the element's tag (both '' when unqualified)."""
        uri = ""
        try:
            uri = etree.QName(node).namespace or ""
        except Exception:
            uri = ""
        prefix = ""
        if uri:
            for p, u in (node.nsmap or {}).items():
                if u == uri:
                    prefix = p or ""
                    break
        return {"uri": uri, "prefix": prefix}

    def _line_end(node):
        try:
            lines = [c.sourceline for c in node.iter() if getattr(c, "sourceline", None)]
            return max(lines) if lines else getattr(node, "sourceline", None)
        except Exception:
            return getattr(node, "sourceline", None)

    def _semantic(tag, attrs, text, kids, is_root):
        label = str(tag).replace("_", " ")
        s = f"Root {label} element" if is_root else label
        if attrs:
            s += " (" + ", ".join(f"{k}={v}" for k, v in attrs.items()) + ")"
        if text:
            s += f": {text}"
        elif kids:
            ct = Counter(_localname(c.tag) for c in kids)
            if len(ct) == 1:
                t, n = next(iter(ct.items()))
                s += f" containing {n} {t} element" + ("s" if n != 1 else "")
            else:
                s += f" containing {len(kids)} child elements"
        return s

    def walk(node, parent_id, depth, xpath, is_root):
        order["n"] += 1
        eid = _new()
        tag = _localname(node.tag)
        attrs = {_localname(k): v for k, v in node.attrib.items()}
        kids = [c for c in node if isinstance(c.tag, str)]

        text = (node.text or "").strip() or None
        normalized = re.sub(r"\s+", " ", text).strip() if text else None
        semantic = _semantic(tag, attrs, text, kids, is_root)

        el = {
            "id": eid, "parent_id": parent_id, "type": "xml_element",
            "hierarchy": {"depth": depth, "level": depth},
            "location": {"xpath": xpath,
                         "line_start": getattr(node, "sourceline", None),
                         "line_end": _line_end(node)},
            "content": {
                "xml_type": "element",
                "tag": tag,
                "namespace": _namespace(node),
                "attributes": attrs,
                "text": text,
                "normalized_text": normalized,
                "semantic_text": semantic,
                "child_count": len(kids),
            },
            "metadata": {"order": order["n"], "confidence": 1.0,
                         "token_estimate": _tok(semantic)},
            "relationships": {"parent": parent_id, "children": [],
                              "previous": None, "next": None},
        }
        elements.append(el)
        id_map[eid] = el

        if kids:
            # positional [n] only when a tag repeats among siblings (canonical XPath)
            counts = Counter(_localname(c.tag) for c in kids)
            seen, ids = {}, []
            for c in kids:
                lt = _localname(c.tag)
                if counts[lt] > 1:
                    seen[lt] = seen.get(lt, 0) + 1
                    seg = f"{lt}[{seen[lt]}]"
                else:
                    seg = lt
                ids.append(walk(c, eid, depth + 1, f"{xpath}/{seg}", False))
            el["relationships"]["children"] = ids
            _link_siblings(ids, id_map)

        text_lines.append(f"{xpath}: {semantic}")   # semantic text feeds chunking
        return eid

    walk(root, None, 1, f"/{_localname(root.tag)}", True)
    return elements, _localname(root.tag), "\n".join(text_lines)
