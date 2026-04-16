import React from "react";
import "../../styles/startpage/footer.css";

const Footer = () => {
  return (
    <footer className="footer">
      {/* grid overlay via ::before in CSS */}

      <div className="footer__container">
        {/* ── Top row ── */}
        <div className="footer__top">
          {/* Brand col */}
          <div className="footer__brand">
            <img
              src="/src/assets/Logo/Agentflowlogo.png"
              alt="AgentFlow"
              className="footer__agentflow-logo footer__agentflow-logo--lg"
              onError={(e) => {
                e.target.style.display = "none";
                e.target.insertAdjacentHTML(
                  "afterend",
                  `<span class="footer__agentflow-fallback">AgentFlow</span>`,
                );
              }}
            />
            <p className="footer__brand-desc">
              Empowering enterprises with intelligent AI agents, RAG chatbots
              and workflow automation — all in one studio.
            </p>
            <div className="footer__welyne">
              <span className="footer__welyne-by">A product by</span>
              <img
                src="/src/assets/Logo/welyne-logo-DWLrWLtB.png"
                alt="Welyne"
                className="footer__welyne-logo"
                onError={(e) => {
                  e.target.style.display = "none";
                  e.target.insertAdjacentHTML(
                    "afterend",
                    `<span class="footer__welyne-fallback">Welyne</span>`,
                  );
                }}
              />
            </div>

            {/* Social icons */}
            <div className="footer__socials">
              <a
                href="https://www.linkedin.com/company/welyne"
                target="_blank"
                rel="noreferrer"
                className="footer__social-link"
                aria-label="LinkedIn"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M20.45 20.45h-3.554v-5.57c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.137 1.446-2.137 2.94v5.667H9.352V9h3.414v1.561h.048c.476-.9 1.637-1.85 3.37-1.85 3.602 0 4.267 2.37 4.267 5.455v6.284zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                </svg>
              </a>
              <a
                href="https://www.facebook.com/profile.php?id=100047803730321"
                target="_blank"
                rel="noreferrer"
                className="footer__social-link"
                aria-label="Facebook"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M24 12.073C24 5.405 18.627 0 12 0S0 5.405 0 12.073C0 18.1 4.388 23.094 10.125 24v-8.437H7.078v-3.49h3.047V9.41c0-3.025 1.792-4.697 4.533-4.697 1.312 0 2.686.235 2.686.235v2.97h-1.513c-1.491 0-1.956.93-1.956 1.874v2.25h3.328l-.532 3.49h-2.796V24C19.612 23.094 24 18.1 24 12.073z" />
                </svg>
              </a>
              <a
                href="https://www.welyne.com"
                target="_blank"
                rel="noreferrer"
                className="footer__social-link"
                aria-label="Welyne website"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="2" y1="12" x2="22" y2="12" />
                  <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
                </svg>
              </a>
            </div>
          </div>

          {/* Product links */}
          <div className="footer__col">
            <h4 className="footer__col-title">Product</h4>
            <ul className="footer__links">
              <li>
                <a href="#services" className="footer__link">
                  RAG Chatbots
                </a>
              </li>
              <li>
                <a href="#services" className="footer__link">
                  AI Agents
                </a>
              </li>
              <li>
                <a href="#services" className="footer__link">
                  Workflows
                </a>
              </li>
              <li>
                <a href="#services" className="footer__link">
                  API Export
                </a>
              </li>
            </ul>
          </div>

          {/* Company links */}
          <div className="footer__col">
            <h4 className="footer__col-title">Company</h4>
            <ul className="footer__links">
              <li>
                <a href="#about" className="footer__link">
                  About
                </a>
              </li>
              <li>
                <a href="#faq" className="footer__link">
                  FAQ
                </a>
              </li>
              <li>
                <a href="mailto:contact@welyne.com" className="footer__link">
                  Contact
                </a>
              </li>
            </ul>
          </div>

          {/* Studio status */}
          <div className="footer__col">
            <h4 className="footer__col-title">Studio</h4>
            <div className="footer__status">
              <span className="footer__status-dot" />
              <span className="footer__status-text">Studio Live — v1.0.0</span>
            </div>
            <p className="footer__studio-note">
              Build, test and deploy your agents without leaving the platform.
            </p>
          </div>
        </div>

        {/* ── Divider ── */}
        <div className="footer__divider" />

        {/* ── Bottom row ── */}
        <div className="footer__bottom">
          <span className="footer__copy">
            © 2026 AgentFlow by Welyne. All rights reserved.
          </span>
          <div className="footer__bottom-logos">
            <img
              src="/src/assets/Logo/Agentflowlogowithouttext.png"
              alt="AgentFlow icon"
              className="footer__bottom-icon"
              onError={(e) => {
                e.target.style.display = "none";
              }}
            />
            <span className="footer__bottom-sep">×</span>
            <img
              src="/src/assets/Logo/welyne-logo-DWLrWLtB.png"
              alt="Welyne"
              className="footer__bottom-welyne"
              onError={(e) => {
                e.target.style.display = "none";
              }}
            />
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
