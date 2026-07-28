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


# ══════════════════════════════════════════════════════════════
#  RECORD DETECTION — enterprise trees are usually collections of
#  repeated business objects (book/book/…, employee/employee/…).
#  Each repeated node becomes a RECORD: searchable field text for the
#  embedding + rich metadata for filtering. Three representations live
#  side by side on the element: structure (tree/relationships),
#  search text (semantic_text), metadata (record_type/id/fields).
# ══════════════════════════════════════════════════════════════

_ID_KEYS = ("id", "key", "code", "ref", "uid", "sku", "isbn", "number")

# Safety ceiling only — records keep their FULL text (a 40k description must
# not be truncated at parse time; the CHUNKER splits oversized records with
# the heading re-prefixed on every piece).
_RECORD_TEXT_CAP = 200_000
_FIELDS_CAP = 12


def _singular(name: str) -> str:
    n = (name or "").strip()
    return n[:-1] if n.endswith("s") and len(n) > 3 else n


def _best_id(pairs: dict):
    for k, v in (pairs or {}).items():
        lk = str(k).lower()
        if (lk in _ID_KEYS or lk.endswith("id") or lk.endswith("_id")) and v not in (None, ""):
            return str(v)
    return None


def _title_line(rtype: str, rid, index: int) -> str:
    label = (rtype or "record").replace("_", " ").strip().capitalize()
    return f"{label} {rid}" if rid else f"{label} {index}"


def _typed_value(v):
    """Infer the field's type — enables typed metadata filtering
    (price > 40, publish_date ranges) instead of string-only matching."""
    s = str(v).strip()
    if isinstance(v, bool) or s.lower() in ("true", "false"):
        return {"type": "boolean", "value": s.lower() == "true" if not isinstance(v, bool) else v}
    if re.fullmatch(r"-?\d+", s):
        try:
            return {"type": "number", "value": int(s)}
        except ValueError:
            pass
    if re.fullmatch(r"-?\d+[.,]\d+", s):
        try:
            return {"type": "number", "value": float(s.replace(",", "."))}
        except ValueError:
            pass
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ].{0,20})?", s) or re.fullmatch(r"\d{2}/\d{2}/\d{4}", s):
        return {"type": "date", "value": s}
    return {"type": "string", "value": s[:120]}


_KW_STOP = {"the", "and", "with", "for", "les", "des", "une", "dans", "pour",
            "avec", "this", "that", "from", "are", "was", "een", "der", "und"}


def _keywords(rtype, rid, fields, cap=10):
    """Compact keyword list for hybrid retrieval (BM25-friendly tokens)."""
    out, seen = [], set()

    def add(tok):
        t = str(tok).strip()
        lt = t.lower()
        if len(t) > 2 and lt not in seen and lt not in _KW_STOP:
            seen.add(lt)
            out.append(t)

    if rtype:
        add(rtype)
    if rid:
        add(rid)
    for fv in fields.values():
        val = fv.get("value") if isinstance(fv, dict) else fv
        for w in re.findall(r"[A-Za-zÀ-ÿ0-9][\w'’-]{2,}", str(val))[:4]:
            add(w)
        if len(out) >= cap:
            break
    return out[:cap]


def _finish_record(el, rtype, collection, rid, lines, fields, index):
    """Attach the record's representations to the element:
       semantic_text  — natural-language field text (for the embedding)
       search_text    — compact tokens only (for lexical/hybrid search)
       metadata       — typed fields + primary_key + keywords (for filtering)"""
    header = _title_line(rtype, rid, index)
    text = "\n".join([header] + lines)[:_RECORD_TEXT_CAP]
    typed = {k: _typed_value(v) for k, v in list(fields.items())[:_FIELDS_CAP]}
    el["content"]["semantic_text"] = text          # ← what gets embedded
    el["content"]["search_text"] = " ".join(
        [str(x) for x in (rtype, rid) if x]
        + [str(f["value"]) for f in typed.values()]
    ).lower()[:600]
    el["metadata"].update({
        "is_record": True,
        "record_type": rtype,
        "record_id": rid,
        "primary_key": rid,          # normalized: employee_id/sku/isbn/… all land here
        "collection": collection,
        "fields": typed,
        "keywords": _keywords(rtype, rid, typed),
    })
    el["metadata"]["token_estimate"] = _tok(text)


def record_sections(elements):
    """One legacy SECTION per record — heading 'Book bk101', body = the field
    text. This is what enterprise parsers produce instead of one giant
    flattened section per collection. Empty list when no records exist."""
    out = []
    for e in elements:
        m = e.get("metadata") or {}
        if not m.get("is_record"):
            continue
        text = (e.get("content") or {}).get("semantic_text") or ""
        head, _, body = text.partition("\n")
        out.append({"heading": head, "content": body or text, "level": 2})
    return out


def mark_xml_records(elements):
    """Detect repeated sibling tags (>=2 container children with the same tag)
    and turn each into a record with searchable text + metadata."""
    from collections import Counter
    by_id = {e["id"]: e for e in elements}

    def leaf_lines(eid, prefix, lines, fields, depth):
        el = by_id[eid]
        c = el["content"]
        tag = str(c.get("tag") or "").replace("_", " ")
        label = f"{prefix} > {tag}" if prefix else tag.capitalize()
        for ak, av in (c.get("attributes") or {}).items():
            lines.append(f"{label} {ak}: {av}")
        kids = el["relationships"]["children"]
        txt = c.get("normalized_text")
        if txt:
            lines.append(f"{label}: {txt}")
            if not prefix:
                fields.setdefault(str(c.get("tag")), str(txt)[:120])
        for k in kids:
            leaf_lines(k, label if depth else "", lines, fields, depth + 1)

    for el in elements:
        kids = [by_id[k] for k in el["relationships"]["children"]]
        groups = Counter(k["content"].get("tag") for k in kids if k["type"] == "xml_element")
        for tag, n in groups.items():
            if n < 2:
                continue
            members = [k for k in kids if k["content"].get("tag") == tag]
            # records are containers (have children or attributes), not plain leaves
            if not all(m["relationships"]["children"] or m["content"].get("attributes")
                       for m in members):
                continue
            collection = el["content"].get("tag") or "document"
            el["metadata"].update({"is_collection": True, "record_count": n})
            for i, m in enumerate(members, start=1):
                lines, fields = [], {}
                for ak, av in (m["content"].get("attributes") or {}).items():
                    lines.append(f"{str(ak).capitalize()}: {av}")
                    fields.setdefault(str(ak), str(av)[:120])
                for k in m["relationships"]["children"]:
                    leaf_lines(k, "", lines, fields, 0)
                rid = _best_id(m["content"].get("attributes")) or _best_id(fields)
                _finish_record(m, _singular(tag), collection, rid, lines, fields, i)


def mark_json_records(elements):
    """Arrays of >=2 objects → each object item becomes a record."""
    by_id = {e["id"]: e for e in elements}

    def leaf_lines(eid, prefix, lines, fields, depth):
        el = by_id[eid]
        c = el["content"]
        key = str(c.get("key") if c.get("key") is not None else "").replace("_", " ")
        label = (f"{prefix} > {key}" if prefix and key else (key or prefix)).strip()
        jt = c.get("json_type")
        if jt in ("object", "array"):
            for k in el["relationships"]["children"]:
                leaf_lines(k, label, lines, fields, depth + 1)
            return
        v = c.get("value")
        if v in (None, ""):
            return
        lines.append(f"{(label or 'value').capitalize()}: {v}")
        if not prefix and key:
            fields.setdefault(str(c.get("key")), str(v)[:120])

    for el in elements:
        if el["type"] != "json_array":
            continue
        kids = [by_id[k] for k in el["relationships"]["children"]]
        members = [k for k in kids if k["type"] == "json_object"]
        if len(members) < 2:
            continue
        key = el["content"].get("key")
        collection = str(key) if key else "items"     # root arrays have no key
        rtype = _singular(collection) if key else "record"
        el["metadata"].update({"is_collection": True, "record_count": len(members)})
        for i, m in enumerate(members, start=1):
            lines, fields = [], {}
            for k in m["relationships"]["children"]:
                leaf_lines(k, "", lines, fields, 0)
            rid = _best_id(fields)
            _finish_record(m, rtype, collection, rid, lines, fields, i)


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
        # keys ONLY — the values live on the child leaves; repeating them here
        # would duplicate every field when container + leaves are both chunked
        label = f"object with {len(keys)} key" + ("s" if len(keys) != 1 else "")
        head = ", ".join(str(k) for k in keys[:6])
        return (f"{key} " if key else "") + label + (f" ({head})" if head else "")
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

    mark_json_records(elements)
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
    mark_xml_records(elements)
    return elements, _localname(root.tag), "\n".join(text_lines)
