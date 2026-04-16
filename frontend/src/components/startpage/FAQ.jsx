import React, { useState } from "react";
import "../../styles/startpage/faq.css";

const faqs = [
  {
    question: "What is AgentFlow?",
    answer:
      "AgentFlow is an enterprise AI studio developed by Welyne. It lets your team build, test and deploy AI-powered agents — including RAG chatbots, autonomous agents and automated workflows — all from a single platform, without needing to write backend code.",
  },
  {
    question: "How do I build a RAG chatbot?",
    answer:
      "Building a RAG chatbot in AgentFlow takes just a few steps. Upload your documents (PDFs, Word files, etc.), configure your chatbot agent, and connect it to your knowledge base. AgentFlow handles the retrieval and AI response pipeline automatically. You can test it live in the studio before making it available to your team.",
  },
  {
    question: "Can I export my agents as an API?",
    answer:
      "Yes. Every agent you build in AgentFlow can be exposed as a REST API endpoint. This means you can build an agent inside the studio and then integrate it into any external application — whether it's a mobile app, a third-party platform or an internal tool — using a simple API call.",
  },
  {
    question: "Is AgentFlow no-code?",
    answer:
      "AgentFlow is designed to be fully no-code for building and deploying agents. You configure your agents through a visual interface — no backend setup, no infrastructure management. For advanced users who want more control, API access and custom integrations are also available.",
  },
];

const ChevronIcon = () => (
  <svg viewBox="0 0 24 24">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const FAQ = () => {
  const [openIndex, setOpenIndex] = useState(null);

  const toggle = (i) => setOpenIndex(openIndex === i ? null : i);

  return (
    <section className="faq" id="faq">
      <div className="faq__glow faq__glow--1" />
      <div className="faq__glow faq__glow--2" />

      <div className="faq__container">
        {/* ── Header ── */}
        <div className="faq__header">
          <div className="faq__badge">
            <span className="faq__badge-dot" />
            FAQ
          </div>
          <h2 className="faq__title">
            Got <span className="faq__title-blue">questions?</span>
          </h2>
          <p className="faq__subtitle">
            Everything you need to know about AgentFlow and how it works.
          </p>
        </div>

        {/* ── Accordion ── */}
        <div className="faq__list">
          {faqs.map((faq, i) => (
            <div
              key={i}
              className={`faq__item ${openIndex === i ? "faq__item--open" : ""}`}
            >
              <button
                className="faq__question"
                onClick={() => toggle(i)}
                aria-expanded={openIndex === i}
              >
                <span className="faq__question-text">{faq.question}</span>
                <span className="faq__chevron">
                  <ChevronIcon />
                </span>
              </button>

              <div className="faq__answer">
                <div className="faq__answer-inner">
                  <p className="faq__answer-text">{faq.answer}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* ── Bottom contact row ── */}
        <div className="faq__bottom">
          <span className="faq__bottom-text">Still have questions?</span>
          <a href="mailto:contact@welyne.com" className="faq__bottom-link">
            Contact Welyne →
          </a>
        </div>
      </div>
    </section>
  );
};

export default FAQ;
