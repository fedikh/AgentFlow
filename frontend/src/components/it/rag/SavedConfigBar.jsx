import React, { useEffect, useState } from "react";
import { listProviders } from "../../../services/providersApi";
import ProviderLogo from "../../ProviderLogo";
import { buildPipelineSections, useEffectiveModels } from "./pipelineConfig";
import "../../../styles/it/flowview.css";

/**
 * SavedConfigBar — compact "currently saved" summary for a single config page.
 * Shown at the top of each config panel so the IT always sees what is persisted
 * (vs. the edits in the form below). Reads the SAVED space object.
 */
const SavedConfigBar = ({ space, panelKey }) => {
  const [providers, setProviders] = useState([]);
  const eff = useEffectiveModels(space);

  useEffect(() => {
    if (panelKey === "llm" || panelKey === "embed") {
      listProviders()
        .then(setProviders)
        .catch(() => setProviders([]));
    }
  }, [panelKey]);

  if (!space) return null;
  const section = buildPipelineSections(space, providers, eff).find(
    (s) => s.key === panelKey,
  );
  if (!section) return null;

  return (
    <div className="scfg" style={{ "--accent": section.accent }}>
      <div className="scfg-head">
        <span className="scfg-eyebrow">Currently saved</span>
        <span className="scfg-title">{section.title}</span>
        {section.family && (
          <span className="scfg-logo">
            <ProviderLogo family={section.family} size={16} />
          </span>
        )}
      </div>
      <div className="scfg-chips">
        {section.rows.map(([k, v]) => (
          <span className="scfg-chip" key={k}>
            <span className="scfg-chip-k">{k}</span>
            <span className="scfg-chip-v">{String(v)}</span>
          </span>
        ))}
      </div>
    </div>
  );
};

export default SavedConfigBar;
