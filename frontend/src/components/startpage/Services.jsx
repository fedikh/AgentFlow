import React from "react";
import "../../styles/startpage/services.css";

const services = [
  {
    img: "/src/assets/startpage/rag.png",
    title: "RAG Chatbots",
    desc: "Upload your documents and instantly build a retrieval-augmented chatbot. Your team can query internal knowledge — policies, manuals, HR docs — through a smart conversational interface.",
    tags: ["Document Q&A", "Knowledge Base", "In-app & API"],
    href: "#",
  },
  {
    img: "/src/assets/startpage/aiagent.png",
    title: "AI Agents",
    desc: "Design intelligent agents that reason, plan and act. Connect them to your tools and data sources to automate complex tasks that would normally require human intervention.",
    tags: ["Autonomous", "Tool Use", "Multi-step"],
    href: "#",
  },
  {
    img: "/src/assets/startpage/workflow.png",
    title: "Workflows",
    desc: "Build automated pipelines that chain agents, models and actions together. Trigger workflows on events, schedules or API calls — and monitor every run in real time.",
    tags: ["Automation", "Event-driven", "Monitoring"],
    href: "#",
  },
];

const Services = () => {
  return (
    <section className="services" id="services">
      <div className="services__container">
        {/* ── Header ── */}
        <div className="services__header">
          <div className="services__badge">
            <span className="services__badge-dot" />
            What We Offer
          </div>
          <h2 className="services__title">
            Everything you need to{" "}
            <span className="services__title-blue">build with AI</span>
          </h2>
          <p className="services__subtitle">
            Three powerful building blocks — combine them to create any
            AI-powered experience your enterprise needs.
          </p>
        </div>

        {/* ── Cards Grid ── */}
        <div className="services__grid">
          {services.map((s) => (
            <div className="services__card" key={s.title}>
              {/* Icon */}
              <div className="services__card-icon">
                <img src={s.img} alt={s.title} />
              </div>

              {/* Body */}
              <div className="services__card-body">
                <h3 className="services__card-title">{s.title}</h3>
                <p className="services__card-desc">{s.desc}</p>
                <div className="services__card-tags">
                  {s.tags.map((tag) => (
                    <span className="services__tag" key={tag}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              {/* Link */}
              <a href={s.href} className="services__card-link">
                Learn more
                <span className="services__card-link-arrow">→</span>
              </a>
            </div>
          ))}
        </div>

        {/* ── Bottom CTA strip ── */}
        <div className="services__cta-strip">
          <p className="services__cta-text">
            Ready to build your first <span>AI agent</span>?
          </p>
          <a href="signup" className="services__cta-btn">
            Start for free →
          </a>
        </div>
      </div>
    </section>
  );
};

export default Services;
