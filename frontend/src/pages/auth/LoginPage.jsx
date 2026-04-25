import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "../../styles/auth/auth.css";
import LeftPanel from "../../components/auth/LeftPanel";
import {
  login,
  saveSession,
  getUser,
  clearSession,
  isLoggedIn,
} from "../../services/authApi";

const LoginPage = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [locked, setLocked] = useState(false);

  // Session check — show "continue as" for IT/USER
  const [existingUser, setExistingUser] = useState(null);

  useEffect(() => {
    if (isLoggedIn()) {
      const user = getUser();
      if (user && user.role === "ADMIN") {
        // Admin → always clear and show login form
        clearSession();
      } else if (user) {
        // IT/USER → show "continue as" prompt
        setExistingUser(user);
      }
    }
  }, []);

  const handleContinue = () => {
    const redirects = { IT: "/it", USER: "/user" };
    navigate(redirects[existingUser.role] || "/dashboard");
  };

  const handleNewLogin = () => {
    clearSession();
    setExistingUser(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (locked) return;
    setError("");
    setLoading(true);
    try {
      const data = await login(email, password);
      saveSession(data);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
      if (err.message.includes("locked") || err.message.includes("Too many")) {
        setLocked(true);
      }
    } finally {
      setLoading(false);
    }
  };

  // ── Continue as existing user ──
  if (existingUser) {
    const initials = existingUser.name
      ? existingUser.name
          .split(" ")
          .map((n) => n[0])
          .join("")
          .toUpperCase()
          .slice(0, 2)
      : "??";

    return (
      <div className="auth-screen">
        <LeftPanel
          title="Welcome back to your"
          highlight="AI studio"
          desc="Build, test and deploy intelligent agents on your enterprise data — all from one platform."
        />
        <div className="right-panel">
          <div className="form-box" style={{ textAlign: "center" }}>
            <div className="continue-avatar">{initials}</div>
            <h1 className="form-title" style={{ marginTop: 16 }}>
              Welcome back!
            </h1>
            <p className="form-sub">You are still logged in as</p>

            <div className="continue-card">
              <div className="continue-info">
                <div className="continue-name">{existingUser.name}</div>
                <div className="continue-email">{existingUser.email}</div>
                <div className="continue-role-row">
                  <span className="continue-role">{existingUser.role}</span>
                  {existingUser.org_name && (
                    <span className="continue-org">
                      {existingUser.org_name}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <button
              className="btn-primary"
              onClick={handleContinue}
              style={{ marginTop: 20 }}
            >
              Continue as {existingUser.name?.split(" ")[0]}
            </button>

            <p className="form-footer" style={{ marginTop: 16 }}>
              Not you?{" "}
              <span className="link" onClick={handleNewLogin}>
                Sign in with a different account
              </span>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Normal login form ──
  return (
    <div className="auth-screen">
      <LeftPanel
        title="Welcome back to your"
        highlight="AI studio"
        desc="Build, test and deploy intelligent agents on your enterprise data — all from one platform."
      />

      <div className="right-panel">
        <form className="form-box" onSubmit={handleSubmit}>
          <h1 className="form-title">Sign in to AgentFlow</h1>
          <p className="form-sub">
            Enter your credentials to access your workspace
          </p>

          {error && <div className="form-error">{error}</div>}

          <div className="field">
            <label>Email address</label>
            <input
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="field">
            <label>Password</label>
            <div className="input-icon-wrap">
              <input
                type={showPass ? "text" : "password"}
                placeholder="••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="input-icon-btn"
                onClick={() => setShowPass(!showPass)}
              >
                {showPass ? (
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div className="forgot">
            <span className="link" onClick={() => navigate("/forgot")}>
              Forgot password?
            </span>
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={loading || locked}
          >
            {loading ? "Signing in..." : locked ? "Account locked" : "Sign in"}
          </button>

          <p className="form-footer">
            Don't have an account?{" "}
            <span className="link" onClick={() => navigate("/signup")}>
              Sign up
            </span>
          </p>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
