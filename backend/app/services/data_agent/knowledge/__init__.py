"""
Knowledge sources — everything the agent knows besides the live schema.

    introspect.py  the database's anatomy + low-cardinality sample values
    imports.py     CSV bulk import for prompt→SQL pairs and the glossary
    space.py       the HIDDEN RAG space that holds business documents —
                   ingestion and retrieval are the platform's existing
                   pipelines (services/providers, services/retrieval), not a
                   second implementation
"""
from .imports import TEMPLATES, import_examples, import_glossary  # noqa: F401
from .introspect import schema_payload, start_introspection  # noqa: F401
from .space import (SYSTEM_KIND, cleanup_orphan_spaces,  # noqa: F401
                    delete_space, ensure_space, get_space, stats)
