import React from "react";

const LeftPanel = ({ title, highlight, desc }) => (
  <div className="left-panel">
    {/* Top — Brand (same as navbar) */}
    <div className="brand">
      <div className="brand-icon-wrap">
        <div className="brand-icon-glow" />
        <div className="brand-icon">
          <img
            src="/src/assets/Logo/Agentflowlogowithouttext.png"
            alt="AgentFlow"
            className="brand-icon-img"
            onError={(e) => {
              e.target.style.display = "none";
              e.target.parentElement.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="white"
                  stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                  width="24" height="24">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                </svg>`;
            }}
          />
        </div>
      </div>
      <div className="brand-text">
        <div className="brand-name">
          AgentFlow<span className="brand-dot">.AI</span>
        </div>
        <div className="brand-sub">AGENTS STUDIO · v1.0</div>
      </div>
    </div>

    {/* Center — Big title + subtitle */}
    <div className="left-center">
      <h2 className="left-tagline">
        {title} <span className="left-highlight">{highlight}</span>
      </h2>
      <p className="left-desc">{desc}</p>
    </div>

    {/* Bottom — Welyne logo */}
    <div className="welyne-row">
      <span className="welyne-by">A product by</span>
      <img
        src="/src/assets/Logo/welyne-logo-DWLrWLtB.png"
        alt="Welyne"
        className="welyne-logo"
        onError={(e) => {
          e.target.style.display = "none";
          e.target.insertAdjacentHTML(
            "afterend",
            `<span class="welyne-fallback">Welyne</span>`,
          );
        }}
      />
    </div>
  </div>
);

export default LeftPanel;
