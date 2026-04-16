import React from "react";
import "../../styles/startpage/about.css";

const About = () => {
  const features = [
    {
      icon: "🏗️",
      title: "Build",
      sub: "Create RAG chatbots, AI agents and automated workflows directly inside the studio — no backend needed.",
    },
    {
      icon: "🧪",
      title: "Test",
      sub: "Run and validate your agents live before deploying — interact, debug and fine-tune in real time.",
    },
    {
      icon: "🚀",
      title: "Deploy & Monitor",
      sub: "Deploy agents inside the platform for your team, or expose them as APIs to plug into any external app.",
    },
  ];

  const capabilities = [
    { icon: "💬", label: "RAG Chatbots" },
    { icon: "🤖", label: "AI Agents" },
    { icon: "🔄", label: "Workflows" },
    { icon: "🔌", label: "API Export" },
    { icon: "📊", label: "Monitoring" },
    { icon: "📁", label: "Doc Ingestion" },
  ];

  return (
    <section className="about" id="about">
      <div className="about__glow about__glow--1" />
      <div className="about__glow about__glow--2" />

      <div className="about__container">
        {/* ── LEFT: Text ── */}
        <div className="about__left">
          <div className="about__badge">
            <span className="about__badge-dot" />
            About AgentFlow
          </div>

          <h2 className="about__heading">
            Your enterprise{" "}
            <span className="about__heading-blue">studio of agents</span>
          </h2>

          <p className="about__desc">
            AgentFlow is the all-in-one platform by{" "}
            <strong className="about__desc-brand">Welyne</strong> where your
            enterprise builds, tests and deploys AI agents — RAG chatbots,
            intelligent workflows and automated assistants — without leaving the
            studio.
          </p>

          <p className="about__desc">
            Upload your documents, configure your agent, and make it available
            to your team inside the platform — or export it as an API to power
            any external application.
          </p>

          <div className="about__features">
            {features.map((f) => (
              <div className="about__feature" key={f.title}>
                <div className="about__feature-icon">{f.icon}</div>
                <div className="about__feature-text">
                  <span className="about__feature-title">{f.title}</span>
                  <span className="about__feature-sub">{f.sub}</span>
                </div>
              </div>
            ))}
          </div>

          <a href="#services" className="about__cta">
            Explore the Studio
            <span className="about__cta-arrow">→</span>
          </a>
        </div>

        {/* ── RIGHT: Visual Card + Welyne ── */}
        <div className="about__right">
          <div className="about__visual">
            <div className="about__card">
              {/* AgentFlow full logo — bigger */}
              <div className="about__card-header">
                <img
                  src="/src/assets/Logo/Agentflowlogo.png"
                  alt="AgentFlow"
                  className="about__card-fulllogo"
                  onError={(e) => {
                    e.target.style.display = "none";
                    e.target.insertAdjacentHTML(
                      "afterend",
                      `
                      <div class="about__card-logo-fallback">
                        <span style="font-size:1.4rem">⚡</span>
                        <div>
                          <div class="about__card-title">AGENTFLOW</div>
                          <div class="about__card-sub">STUDIO OF AGENTS</div>
                        </div>
                      </div>`,
                    );
                  }}
                />
              </div>

              {/* Capabilities grid */}
              <div className="about__capabilities">
                <div className="about__cap-label">What you can build</div>
                <div className="about__cap-grid">
                  {capabilities.map((c) => (
                    <div className="about__cap-item" key={c.label}>
                      <span className="about__cap-icon">{c.icon}</span>
                      <span className="about__cap-text">{c.label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Status bar */}
              <div className="about__status">
                <div className="about__status-left">
                  <span className="about__status-dot" />
                  Studio Live
                </div>
                <span className="about__status-ver">v1.0.0</span>
              </div>
            </div>

            {/* Welyne — below the card */}
            <div className="about__welyne-row">
              <span className="about__welyne-by">A product by</span>
              <img
                src="/src/assets/Logo/welyne-logo-DWLrWLtB.png"
                alt="Welyne"
                className="about__welyne-img"
                onError={(e) => {
                  e.target.style.display = "none";
                  e.target.insertAdjacentHTML(
                    "afterend",
                    `<span class="about__welyne-fallback">Welyne</span>`,
                  );
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default About;
