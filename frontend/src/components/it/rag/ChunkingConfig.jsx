import React, { useState } from "react";

/*
 * Catalog-driven chunking configuration (compact).
 *
 *   SINGLE       — one strategy PER FORMAT: pick the strategy that fits each
 *                  format present (pdf → …, pptx → …, csv → …). Stored in
 *                  cfg.chunk_format_map = { file_type: {strategy, params} }.
 *   PER_DOCUMENT — each parsed document picks its own strategy + params.
 *
 * Strategies, the per-format allow-list and their parameters all come from the
 * backend catalog (GET /rag/chunking/catalog) — nothing is hardcoded.
 */

const FT_LABEL = {
  pdf: "PDF", docx: "Word", pptx: "PowerPoint", txt: "Text", md: "Markdown",
  markdown: "Markdown", json: "JSON", xml: "XML", csv: "CSV", xlsx: "Excel",
  xls: "Excel", html: "HTML", htm: "HTML", url: "Web page",
};

const lc = (s) => (s || "").toLowerCase();
const catOf = (catalog, ft) => catalog?.file_category?.[lc(ft)] || "documents";
const stratsOfCat = (catalog, cat) => catalog?.categories?.[cat]?.strategies || [];

/* Strategies valid for a file type (allow-list filtered + ordered), with the
 * per-type recommended flag applied. */
const stratsOfType = (catalog, ft) => {
  const key = lc(ft);
  const all = stratsOfCat(catalog, catOf(catalog, key));
  const byName = Object.fromEntries(all.map((s) => [s.name, s]));
  const allowed = catalog?.allowed?.[key];
  const list = allowed ? allowed.map((n) => byName[n]).filter(Boolean) : all;
  const rec = catalog?.recommended?.[key];
  return list.map((s) => ({ ...s, recommended: s.name === rec }));
};

const findStrat = (strats, name) => strats.find((s) => s.name === name);
const defaultsOf = (strat) =>
  Object.fromEntries((strat?.params || []).map((p) => [p.key, p.default]));

/* One tunable parameter input (int/float/bool/select) from the catalog schema. */
function ParamInput({ def, value, onChange }) {
  const v = value ?? def.default;
  if (def.type === "bool") {
    return (
      <label className="rag-ck-param rag-ck-param-bool">
        <input type="checkbox" checked={!!v} onChange={(e) => onChange(e.target.checked)} />
        <span>{def.label}</span>
      </label>
    );
  }
  if (def.type === "select") {
    return (
      <label className="rag-ck-param">
        <span className="rag-ck-param-lbl">{def.label}</span>
        <select className="rag-ck-select" value={v} onChange={(e) => onChange(e.target.value)}>
          {(def.options || []).map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label className="rag-ck-param">
      <span className="rag-ck-param-lbl">{def.label}</span>
      <input
        type="number"
        min={def.min}
        max={def.max}
        step={def.step || 1}
        value={v}
        onChange={(e) =>
          onChange(def.type === "float" ? parseFloat(e.target.value) : parseInt(e.target.value, 10))
        }
      />
    </label>
  );
}

function ParamGrid({ strat, params, onParam }) {
  if (!strat?.params?.length)
    return <div className="rag-ck-noparams">This strategy has no parameters.</div>;
  return (
    <div className="rag-ck-params">
      {strat.params.map((p) => (
        <ParamInput key={p.key} def={p} value={params?.[p.key]} onChange={(val) => onParam(p.key, val)} />
      ))}
    </div>
  );
}

/* A compact strategy dropdown for one format/document. */
function StrategySelect({ strats, value, onChange, allowDefault, className = "rag-ck-select" }) {
  return (
    <select className={className} value={value} onChange={(e) => onChange(e.target.value)}>
      {allowDefault && <option value="">Default (space)</option>}
      {strats.map((s) => (
        <option key={s.name} value={s.name}>
          {s.label}{s.recommended ? "  ★ recommended" : ` · ${"★".repeat(s.stars || 0)}`}
        </option>
      ))}
    </select>
  );
}

export default function ChunkingConfig({
  cfg,
  setC,
  catalog,
  parsedDocs = [],
  extractedCount = 0,
  handleSetDocChunking = () => {},
  handleChunkModeChange = null,
  handleProcess = () => {},
  handleProcessAll = () => {},
  processing = false,
  openModal = () => {},
  canBuild = true,
}) {
  const changeMode = handleChunkModeChange || ((m) => setC("chunk_mode", m));
  const [open, setOpen] = useState({});   // which format rows have params expanded
  const rawMode = (cfg.chunk_mode || "SINGLE").toUpperCase();
  const mode =
    rawMode === "PER_DOCUMENT" ? "PER_DOCUMENT" : rawMode === "AGENTIC" ? "AGENTIC" : "SINGLE";

  if (!catalog) return <div className="rag-cfg-hint">Loading chunking strategies…</div>;

  const typesPresent = Array.from(
    new Set(parsedDocs.map((d) => lc(d.file_type)).filter(Boolean))
  );
  const typesToShow = typesPresent.length ? typesPresent : ["pdf"];

  // SINGLE = one strategy per format, in cfg.chunk_format_map.
  const fmtMap = cfg.chunk_format_map || {};
  const effStrategy = (ft) => fmtMap[lc(ft)]?.strategy || catalog.recommended?.[lc(ft)] || "recursive";
  const setFormat = (ft, strategy, params) =>
    setC("chunk_format_map", { ...fmtMap, [lc(ft)]: { strategy, params } });

  return (
    <>
      {/* ── Mode ── */}
      <label className="rag-cfg-label">Chunking mode</label>
      <div className="rag-cfg-cards">
        {[
          { k: "SINGLE", n: "Single", d: "One strategy per format" },
          { k: "PER_DOCUMENT", n: "Per document", d: "Pick a strategy per file" },
          { k: "AGENTIC", n: "Agentic", d: "AI plans & builds the chunks", badge: "AI" },
        ].map((m) => (
          <button
            key={m.k}
            className={`rag-cfg-card ${mode === m.k ? "active" : ""}`}
            onClick={() => changeMode(m.k)}
          >
            <div className="rag-cfg-card-n">
              {m.n}
              {m.badge && <span className="rag-cfg-card-badge">{m.badge}</span>}
            </div>
            <div className="rag-cfg-card-d">{m.d}</div>
          </button>
        ))}
      </div>

      {/* ── AGENTIC: pipeline diagram + tuning ── */}
      {mode === "AGENTIC" && (
        <AgenticPanel
          catalog={catalog}
          params={cfg.chunk_params || {}}
          onParam={(key, val) => setC("chunk_params", { ...(cfg.chunk_params || {}), [key]: val })}
        />
      )}

      {/* ── SINGLE: one strategy per format (compact) ── */}
      {mode === "SINGLE" && (
        <div className="rag-ck-fmtlist">
          <div className="rag-ck-fmtlist-t">Strategy per format</div>
          {typesToShow.map((ft) => {
            const strats = stratsOfType(catalog, ft);
            const name = effStrategy(ft);
            const strat = findStrat(strats, name) || strats[0];
            const params = fmtMap[lc(ft)]?.params || defaultsOf(strat);
            const isOpen = !!open[ft];
            return (
              <div key={ft} className="rag-ck-fmtrow">
                <div className="rag-ck-fmtrow-main">
                  <span className="rag-ck-fmt-chip">{FT_LABEL[ft] || ft.toUpperCase()}</span>
                  <StrategySelect
                    strats={strats}
                    value={name}
                    onChange={(n) => setFormat(ft, n, defaultsOf(findStrat(strats, n)))}
                  />
                  {strat?.params?.length > 0 && (
                    <button
                      type="button"
                      className={`rag-ck-gear ${isOpen ? "on" : ""}`}
                      title="Parameters"
                      onClick={() => setOpen((o) => ({ ...o, [ft]: !o[ft] }))}
                    >
                      ⚙
                    </button>
                  )}
                </div>
                {strat?.pros && <div className="rag-ck-fmtrow-pros">{strat.pros}</div>}
                {isOpen && strat?.params?.length > 0 && (
                  <div className="rag-ck-fmtrow-params">
                    <ParamGrid
                      strat={strat}
                      params={params}
                      onParam={(key, val) => setFormat(ft, name, { ...params, [key]: val })}
                    />
                  </div>
                )}
              </div>
            );
          })}
          {!typesPresent.length && (
            <div className="rag-cfg-hint">
              Showing defaults — parse documents to configure their formats.
            </div>
          )}
        </div>
      )}

      {mode === "PER_DOCUMENT" && (
        <div className="rag-cfg-hint">
          Pick a strategy and tune its parameters for each document below, then
          Process to chunk &amp; index it.
        </div>
      )}

      {/* ── Documents · indexing ── */}
      <div style={{ borderTop: "1px solid var(--rag-border, #e2e8f0)", margin: "18px 0 12px" }} />
      <div className="rag-cfg-head" style={{ marginBottom: 6 }}>
        <label className="rag-cfg-label" style={{ margin: 0 }}>
          {mode === "PER_DOCUMENT" ? "Per-document strategy & indexing" : "Documents · indexing"}
        </label>
        {canBuild && extractedCount > 0 && (
          <button className="rag-btn rag-btn-sm rag-btn-dark" onClick={handleProcessAll} disabled={processing}>
            {processing ? "…" : `Process all (${extractedCount})`}
          </button>
        )}
      </div>

      {parsedDocs.length === 0 && (
        <div className="rag-cfg-hint">
          No parsed documents yet. Upload files and run Load + Parse in the Uploads
          section first.
        </div>
      )}

      <div className="rag-ck-doclist">
        {parsedDocs.map((d) => (
          <DocRow
            key={d.id}
            d={d}
            catalog={catalog}
            mode={mode}
            effLabel={
              (findStrat(stratsOfType(catalog, d.file_type), effStrategy(d.file_type)) || {}).label
              || effStrategy(d.file_type)
            }
            onSetChunking={handleSetDocChunking}
            onProcess={handleProcess}
            processing={processing}
            openModal={openModal}
            canBuild={canBuild}
          />
        ))}
      </div>
    </>
  );
}

/* Agentic mode panel: the pipeline diagram + its tuning parameters. */
function AgenticPanel({ catalog, params, onParam }) {
  const agentic = catalog?.agentic || {};
  const stages = agentic.stages || [];
  const paramDefs = agentic.params || [];

  return (
    <div className="ag-panel">
      <div className="ag-panel-head">
        <span className="ag-panel-badge">AI PIPELINE</span>
        <span className="ag-panel-sub">
          A team of OpenAI agents analyzes each document and builds meaning-based chunks.
        </span>
      </div>

      {/* flow: Parser → [6 agents] → Embedding → Vector DB */}
      <div className="ag-flow">
        <div className="ag-io">Parser</div>
        <div className="ag-flow-arrow">↓</div>
        {stages.map((s, i) => (
          <React.Fragment key={s.key}>
            <div className="ag-stage">
              <span className="ag-stage-num">{i + 1}</span>
              <div className="ag-stage-body">
                <div className="ag-stage-name">{s.label}</div>
                <div className="ag-stage-desc">{s.desc}</div>
              </div>
            </div>
            <div className="ag-flow-arrow">↓</div>
          </React.Fragment>
        ))}
        <div className="ag-io ag-io-out">Embedding</div>
        <div className="ag-flow-arrow">↓</div>
        <div className="ag-io ag-io-out">Vector database</div>
      </div>

      {/* tuning */}
      {paramDefs.length > 0 && (
        <>
          <div className="ag-tune-t">Pipeline settings</div>
          <div className="rag-ck-params">
            {paramDefs.map((p) => (
              <ParamInput
                key={p.key}
                def={p}
                value={params?.[p.key]}
                onChange={(val) => onParam(p.key, val)}
              />
            ))}
          </div>
        </>
      )}

      <div className="ag-note">
        Needs an OpenAI key (space LLM, company provider, or server key). Without one,
        agentic chunking falls back to structural chunking automatically.
      </div>
    </div>
  );
}

/* One parsed-document row: name/status + (per-doc) strategy select & params. */
function DocRow({ d, catalog, mode, effLabel, onSetChunking, onProcess, processing, openModal, canBuild = true }) {
  const strats = stratsOfType(catalog, d.file_type);
  const perDoc = mode === "PER_DOCUMENT";
  const active = d.chunk_strategy || "";
  const strat = findStrat(strats, active);
  const params = d.chunk_params || {};

  const onStrategy = (name) =>
    name ? onSetChunking(d.id, name, defaultsOf(findStrat(strats, name))) : onSetChunking(d.id, "", null);
  const onParam = (key, val) => onSetChunking(d.id, active, { ...params, [key]: val });

  const indexed = d.status === "INDEXED";
  return (
    <div className="rag-ck-doc">
      <div className="rag-ck-doc-head">
        <span className="rag-ck-doc-ft">{(d.file_type || "?").toUpperCase()}</span>
        <div className="rag-ck-doc-info">
          <div className="rag-ck-doc-name">{d.file_name}</div>
          <div className="rag-ck-doc-note">
            {indexed ? (
              <span className="rag-ck-dot ok" />
            ) : d.status === "PROCESSING" ? (
              <span className="rag-ck-dot busy" />
            ) : (
              <span className="rag-ck-dot" />
            )}
            {indexed
              ? `Indexed · ${d.num_chunks || 0} chunks`
              : d.status === "PROCESSING"
                ? "Processing…"
                : "Parsed — not indexed"}
          </div>
        </div>

        {perDoc && canBuild ? (
          <StrategySelect
            strats={strats}
            value={active}
            onChange={onStrategy}
            allowDefault
            className="rag-ck-select rag-ck-select-doc"
          />
        ) : (
          <span className="rag-doc-strategy-fixed">
            {mode === "AGENTIC" ? "Agentic" : perDoc ? strat?.label || active || "default" : effLabel}
          </span>
        )}

        {canBuild && (
          <button className="rag-btn rag-btn-xs rag-btn-dark" onClick={() => onProcess(d.id)} disabled={processing}>
            {indexed ? "Re-index" : "Process"}
          </button>
        )}
        {indexed && (
          <button className="rag-btn rag-btn-xs" onClick={() => openModal("chunks", d)}>
            View
          </button>
        )}
      </div>

      {perDoc && strat?.params?.length > 0 && (
        <div className="rag-ck-doc-params">
          <ParamGrid strat={strat} params={params} onParam={onParam} />
        </div>
      )}
    </div>
  );
}
