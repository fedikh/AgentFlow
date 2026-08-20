"""
Data Agent — natural language → SQL, as a production component.

    sources.py       connection records, lifecycle, authorization
    jobs.py          background job registry (thread + polling)
    config.py        Pydantic config: generation · retrieval · chunking
    state.py         the LangGraph state + decision trace
    graph.py         the workflow (bounded correction loop)
    orchestrator.py  public entry: ask / execute / sessions

    nodes/           one file per graph step
    validators/      the five-check safety chain (sqlglot)
    vanna/           SQL intelligence: store · client · training · prompts
    database/        adapters + pooled, read-only connection manager
    knowledge/       schema introspection + document ingestion (RAG parsers)
    retrieval/       hybrid search over the three knowledge indexes

Responsibility split: Vanna generates SQL, LangGraph controls the workflow,
the validators decide what is allowed to touch a customer database.
"""
