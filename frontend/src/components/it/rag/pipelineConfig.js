import { useEffect, useState } from "react";
import { getProviderModels } from "../../../services/providersApi";
import { getEmbeddingModels } from "../../../services/ragApi";

/**
 * pipelineConfig — single source of truth for "what is saved" per pipeline
 * stage. Both the flow view (FlowPanel) and each config page's saved summary
 * (SavedConfigBar) read from here, so they can never drift apart.
 */

const pct = (v) => `${Math.round((Number(v) || 0) * 100)}%`;

const FT_LABEL = {
  pdf: "PDF", docx: "Word", pptx: "PowerPoint", txt: "Text", md: "Markdown",
  markdown: "Markdown", json: "JSON", xml: "XML", csv: "CSV", xlsx: "Excel",
  xls: "Excel", html: "HTML", htm: "HTML", url: "Web",
};

const isPerDoc = (space) =>
  String(space.chunk_mode || "SINGLE").toUpperCase() === "PER_DOCUMENT";

// Compact summary line for the chunking stage.
const chunkSummary = (space) => {
  if (isPerDoc(space)) return "Per document";
  const map = space.chunk_format_map || {};
  const n = Object.keys(map).length;
  return n ? `Single · ${n} format${n > 1 ? "s" : ""}` : "Single";
};

// Detailed rows: Single mode lists the strategy chosen for each format;
// Per-document defers to each file. (chunk_size/overlap chars are legacy — the
// per-format strategies carry their own parameters now.)
const chunkRows = (space) => {
  if (isPerDoc(space)) {
    return [["Mode", "Per document"], ["Strategy", "Chosen per file"]];
  }
  const map = space.chunk_format_map || {};
  const entries = Object.entries(map);
  const rows = [["Mode", "Single (per format)"]];
  if (entries.length) {
    for (const [ft, v] of entries) {
      rows.push([FT_LABEL[ft] || ft.toUpperCase(), v?.strategy || "—"]);
    }
  } else {
    rows.push(["Strategy", space.chunk_strategy || "recursive"]);
  }
  return rows;
};

function llmSource(space, providers) {
  if (space.llm_has_own_key)
    return { label: "My own key", family: space.llm_provider };
  if (space.llm_provider_id) {
    const p = providers.find((x) => x.id === space.llm_provider_id);
    return {
      label: `Company · ${p?.name || space.llm_provider_id}`,
      family: p?.family || space.llm_provider,
    };
  }
  return { label: "Local · Ollama", family: "OLLAMA" };
}

function embSource(space, providers) {
  if (space.embedding_has_own_key)
    return { label: "My own key", family: space.embedding_provider };
  if (space.embedding_provider_id) {
    const p = providers.find((x) => x.id === space.embedding_provider_id);
    return {
      label: `Company · ${p?.name || space.embedding_provider_id}`,
      family: p?.family || space.embedding_provider,
    };
  }
  return { label: "Local · BGE-M3", family: "LOCAL" };
}

/**
 * useEffectiveModels — resolves the model that will ACTUALLY run for a
 * company-provider source, mirroring the backend resolver: if the saved model
 * doesn't belong to the provider's family, the first catalog model is used.
 * This keeps the overview honest when a stale model (e.g. an Ollama model left
 * over after switching to a Company OpenAI source) is still stored.
 */
export function useEffectiveModels(space) {
  const [eff, setEff] = useState({});

  useEffect(() => {
    if (!space) return;
    let alive = true;

    const resolveLlm = async () => {
      if (!space.llm_provider_id) return undefined;
      try {
        const r = await getProviderModels(space.llm_provider_id, "LLM");
        const ids = (r.models || []).map((m) => m.id);
        if (!ids.length) return space.llm_model;
        return ids.includes(space.llm_model) ? space.llm_model : ids[0];
      } catch {
        return space.llm_model;
      }
    };

    // Embedding: resolve BOTH the effective model and its true dimension.
    const resolveEmb = async () => {
      if (space.embedding_provider_id) {
        try {
          const r = await getProviderModels(space.embedding_provider_id, "EMBEDDING");
          const models = r.models || [];
          const found =
            models.find((m) => m.id === space.embedding_model) || models[0];
          return found ? { model: found.id, dim: found.dim } : {};
        } catch {
          return {};
        }
      }
      // Local (or own key): look up dim from the local embedding catalog.
      try {
        const r = await getEmbeddingModels();
        const found = (r.models || []).find((m) => m.id === space.embedding_model);
        return found ? { dim: found.dim } : {};
      } catch {
        return {};
      }
    };

    (async () => {
      const [llm, emb] = await Promise.all([resolveLlm(), resolveEmb()]);
      if (alive) setEff({ llm, emb: emb.model, embDim: emb.dim });
    })();

    return () => {
      alive = false;
    };
  }, [
    space?.llm_provider_id,
    space?.embedding_provider_id,
    space?.llm_model,
    space?.embedding_model,
  ]);

  return eff;
}

/**
 * Returns the ordered pipeline sections for a space.
 * `overrides` = { llm, emb } effective model ids (from useEffectiveModels).
 * Each: { key, accent, title, tag, how, family?, summary, rows:[[k,v]] }
 */
export function buildPipelineSections(space, providers = [], overrides = {}) {
  if (!space) return [];
  const llm = llmSource(space, providers);
  const emb = embSource(space, providers);
  const sem = space.semantic_weight ?? 0.7;

  const embModel = overrides.emb || space.embedding_model || "BAAI/bge-m3";
  const llmModel =
    overrides.llm || space.llm_model || space.llm_provider || "Not set";

  return [
    {
      key: "docs",
      accent: "#64748b",
      title: "Documents",
      tag: "Ingest",
      how: "Files you upload are loaded and parsed into clean text, tables and images before anything else runs.",
      summary: `${space.num_documents ?? 0} docs · ${space.num_chunks ?? 0} chunks`,
      rows: [
        ["Documents", space.num_documents ?? 0],
        ["Indexed chunks", space.num_chunks ?? 0],
        ["Status", space.status || "DRAFT"],
      ],
    },
    {
      key: "chunk",
      accent: "#0ea5e9",
      title: "Chunking",
      tag: "Split",
      how: "Splits each parsed document into chunks using the strategy that fits its format (headings, slides, rows, tree nodes…), preserving structure for retrieval.",
      summary: chunkSummary(space),
      rows: chunkRows(space),
    },
    {
      key: "embed",
      accent: "#8b5cf6",
      title: "Embedding",
      tag: "Vectorize",
      how: "Turns every chunk into a 1024-dim vector in pgvector. The same model embeds the question at query time, so similar meaning = nearby vectors.",
      family: emb.family,
      summary: embModel.split("/").pop(),
      rows: [
        ["Source", emb.label],
        ["Model", embModel.split("/").pop()],
        ["Dimensions", overrides.embDim ? `${overrides.embDim}d` : "—"],
      ],
    },
    {
      key: "llm",
      accent: "#2563eb",
      title: "LLM",
      tag: "Generate",
      how: "Generates the final answer from the retrieved chunks. Lower temperature = more factual; the system prompt sets tone and rules.",
      family: llm.family,
      summary: llmModel,
      rows: [
        ["Source", llm.label],
        ["Model", llmModel],
        ["Temperature", space.llm_temperature ?? 0.2],
        ["Max tokens", space.llm_max_tokens ?? 1024],
        ["System prompt", space.system_prompt ? "Custom" : "Default"],
      ],
    },
    {
      key: "retrieval",
      accent: "#10b981",
      title: "Retrieval",
      tag: "Search",
      how: "Finds the most relevant chunks with hybrid search — semantic similarity blended with keyword matching — then optionally re-ranks with the LLM.",
      summary: `${pct(sem)} sem · top-${space.top_k ?? 5}`,
      rows: [
        ["Engine", space.search_engine || "HYBRID"],
        ["Semantic / keyword", `${pct(sem)} / ${pct(1 - sem)}`],
        ["Top-K", space.top_k ?? 5],
        ["Reranking", space.reranking_enabled ? "On" : "Off"],
      ],
    },
    {
      key: "eval",
      accent: "#f59e0b",
      title: "Evaluation",
      tag: "Test",
      how: "Manually test the whole configuration: ask questions in the Evaluation tab and inspect the answer and retrieved sources before deploying.",
      summary: "Manual test chat",
      rows: [
        ["Method", "Manual test chat"],
        ["Shows sources", "Yes"],
        ["Space status", space.status || "DRAFT"],
      ],
    },
  ];
}
