import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import "../../styles/auth/auth.css";
import LeftPanel from "../../components/auth/LeftPanel";
import { register, saveSession } from "../../services/authApi";

// ── Account type card ────────────────────────────────
const AccountTypeCard = ({ selected, onClick, icon, title, desc, tags }) => (
  <div
    className={`account-type-card ${selected ? "selected" : ""}`}
    onClick={onClick}
  >
    <div className="account-type-top">
      <div className="account-type-icon">{icon}</div>
      <div className="account-type-radio">
        <div className={`radio-dot ${selected ? "active" : ""}`} />
      </div>
    </div>
    <div className="account-type-title">{title}</div>
    <div className="account-type-desc">{desc}</div>
    <div className="account-type-tags">
      {tags.map((t, i) => (
        <span key={i} className={`tag ${selected ? "tag-active" : ""}`}>{t}</span>
      ))}
    </div>
  </div>
);

// ── Sign Up ──────────────────────────────────────────
const SignUpPage = () => {
  const navigate = useNavigate();

  const [step,      setStep]     = useState(1);
  const [orgType,   setOrgType]  = useState("PERSONAL");
  const [firstName, setFirst]    = useState("");
  const [lastName,  setLast]     = useState("");
  const [email,     setEmail]    = useState("");
  const [orgName,   setOrgName]  = useState("");
  const [password,  setPassword] = useState("");
  const [loading,   setLoading]  = useState(false);
  const [error,     setError]    = useState("");

  const isPersonal = orgType === "PERSONAL";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const payload = {
        first_name: firstName,
        last_name:  lastName,
        email,
        password,
        org_type:   orgType,
        org_name:   isPersonal ? null : orgName,
      };
      const data = await register(payload);
      saveSession(data);           // save token + user in localStorage
      navigate("/dashboard");      // redirect after signup
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const leftProps = isPersonal
    ? {
        title: "Your personal",
        highlight: "AI workspace",
        desc: "One account, full access. Build RAG chatbots, agents and workflows — just for you.",
      }
    : {
        title: "Your enterprise",
        highlight: "agent studio",
        desc: "Invite your IT team and end users. Manage departments and agents from one place.",
      };

  return (
    <div className="auth-screen">
      <LeftPanel {...leftProps} />

      <div className="right-panel">
        <div className="form-box">

          {/* Step indicator */}
          <div className="signup-steps">
            <div className={`signup-step ${step >= 1 ? "done" : ""}`}>
              <div className="signup-step-num">1</div>
              <span>Account type</span>
            </div>
            <div className="signup-step-line" />
            <div className={`signup-step ${step >= 2 ? "done" : ""}`}>
              <div className="signup-step-num">2</div>
              <span>Your details</span>
            </div>
          </div>

          {/* ══ STEP 1 — Account type ══ */}
          {step === 1 && (
            <div>
              <h1 className="form-title">Choose your account type</h1>
              <p className="form-sub">You can always upgrade to Business later</p>

              <div className="account-type-grid">
                <AccountTypeCard
                  selected={orgType === "PERSONAL"}
                  onClick={() => setOrgType("PERSONAL")}
                  icon="👤"
                  title="Personal"
                  desc="Just you — full access, no team management."
                  tags={["RAG", "Agents", "Workflows", "API"]}
                />
                <AccountTypeCard
                  selected={orgType === "BUSINESS"}
                  onClick={() => setOrgType("BUSINESS")}
                  icon="🏢"
                  title="Business"
                  desc="An organization — invite your team and manage access."
                  tags={["Team", "Roles", "Multi-dept", "Admin"]}
                />
              </div>

              <button className="btn-primary" onClick={() => setStep(2)}>
                Continue →
              </button>

              <p className="form-footer">
                Already have an account?{" "}
                <span className="link" onClick={() => navigate("/login")}>
                  Sign in
                </span>
              </p>
            </div>
          )}

          {/* ══ STEP 2 — Details ══ */}
          {step === 2 && (
            <form onSubmit={handleSubmit}>
              <div className="step2-header">
                <span className="link step-back" onClick={() => setStep(1)}>
                  ← Back
                </span>
                <div className="step2-badge">
                  {isPersonal ? "👤 Personal" : "🏢 Business"}
                </div>
              </div>

              <h1 className="form-title">
                {isPersonal ? "Your details" : "Set up your organization"}
              </h1>
              <p className="form-sub">
                {isPersonal
                  ? "A personal workspace will be created automatically."
                  : "You will be the Admin of this organization."}
              </p>

              {error && <div className="form-error">{error}</div>}

              {/* Business only */}
              {!isPersonal && (
                <div className="field">
                  <label>Organization name</label>
                  <input
                    type="text"
                    placeholder="Welyne Ltd."
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
              )}

              <div className="row-2">
                <div className="field">
                  <label>First name</label>
                  <input
                    type="text"
                    placeholder="Fedi"
                    value={firstName}
                    onChange={(e) => setFirst(e.target.value)}
                    required
                    autoFocus={isPersonal}
                  />
                </div>
                <div className="field">
                  <label>Last name</label>
                  <input
                    type="text"
                    placeholder="Khala"
                    value={lastName}
                    onChange={(e) => setLast(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="field">
                <label>Email address</label>
                <input
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="field">
                <label>Password</label>
                <input
                  type="password"
                  placeholder="Min. 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <div className={`signup-info-banner ${isPersonal ? "personal" : "business"}`}>
                <span className="banner-icon">ℹ</span>
                {isPersonal
                  ? "You will be the only user. Member management is disabled for Personal accounts."
                  : "You will be created as Admin. You can invite IT and End Users after signup."}
              </div>

              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? "Creating account..." : "Create account"}
              </button>

              <p className="form-footer">
                Already have an account?{" "}
                <span className="link" onClick={() => navigate("/login")}>
                  Sign in
                </span>
              </p>
            </form>
          )}

        </div>
      </div>
    </div>
  );
};

export default SignUpPage;