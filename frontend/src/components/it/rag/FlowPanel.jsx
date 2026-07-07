import React, { useEffect, useState, useRef } from "react";
import { listProviders } from "../../../services/providersApi";
import ProviderLogo from "../../ProviderLogo";
import { buildPipelineSections, useEffectiveModels } from "./pipelineConfig";
import "../../../styles/it/flowview.css";

/**
 * FlowPanel — the "View flow" page. Two synced parts:
 *   1. A horizontal pipeline rail (Documents → … → Evaluation).
 *   2. Detail cards showing HOW each stage works and the exact config saved.
 * Clicking a node highlights and scrolls to its detail card.
 */
const num = (i) => String(i + 1).padStart(2, "0");

const FlowPanel = ({ space }) => {
  const [providers, setProviders] = useState([]);
  const [active, setActive] = useState(null);
  const cardRefs = useRef({});
  const eff = useEffectiveModels(space);

  useEffect(() => {
    listProviders()
      .then(setProviders)
      .catch(() => setProviders([]));
  }, []);

  if (!space) return null;
  const sections = buildPipelineSections(space, providers, eff);

  const focus = (key) => {
    setActive(key);
    cardRefs.current[key]?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  };

  return (
    <div className="pf">
      <div className="pf-head">
        <div>
          <div className="pf-title">Pipeline</div>
          <div className="pf-sub">
            How documents move from upload to answer — and the exact
            configuration saved for <strong>{space.name}</strong>.
          </div>
        </div>
        <span
          className={`pf-status pf-status-${(space.status || "DRAFT").toLowerCase()}`}
        >
          {space.status || "DRAFT"}
        </span>
      </div>

      {/* ── Flow rail ── */}
      <div className="pf-rail-wrap">
        <div className="pf-rail">
          {sections.map((s, i) => (
            <React.Fragment key={s.key}>
              <button
                type="button"
                className={`pf-step ${active === s.key ? "active" : ""}`}
                style={{ "--accent": s.accent }}
                onClick={() => focus(s.key)}
              >
                <span className="pf-step-top">
                  <span className="pf-step-num">{num(i)}</span>
                  <span className="pf-step-dot" />
                </span>
                <span className="pf-step-tag">{s.tag}</span>
                <span className="pf-step-title">{s.title}</span>
                <span className="pf-step-sum">
                  {s.family && <ProviderLogo family={s.family} size={13} />}
                  <span className="pf-step-sum-t">{s.summary}</span>
                </span>
              </button>
              {i < sections.length - 1 && <span className="pf-rail-line" />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* ── Detail cards ── */}
      <div className="pf-cards">
        {sections.map((s, i) => (
          <div
            key={s.key}
            ref={(el) => (cardRefs.current[s.key] = el)}
            className={`pf-card ${active === s.key ? "active" : ""}`}
            style={{ "--accent": s.accent }}
          >
            <div className="pf-card-head">
              <span className="pf-card-eyebrow">
                <span className="pf-card-num">{num(i)}</span>
                <span className="pf-card-tag">{s.tag}</span>
              </span>
              {s.family && (
                <span className="pf-card-logo">
                  <ProviderLogo family={s.family} size={18} />
                </span>
              )}
            </div>
            <div className="pf-card-title">{s.title}</div>
            <div className="pf-card-how">{s.how}</div>
            <dl className="pf-rows">
              {s.rows.map(([k, v]) => (
                <div className="pf-row" key={k}>
                  <dt className="pf-row-k">{k}</dt>
                  <dd className="pf-row-v">{String(v)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FlowPanel;
