import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "../../styles/auth/auth.css";
import LeftPanel from "../../components/auth/LeftPanel";
import { login, saveSession, isLoggedIn } from "../../services/authApi";

const EyeIcon = ({ open }) => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    {open ? (
      <>
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ) : (
      <>
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
        <line x1="1" y1="1" x2="23" y2="23" />
      </>
    )}
  </svg>
);

// ── Rate limiter (client-side, 3 attempts → 30s lockout) ──
const LOCKOUT_DURATION = 30; // seconds
const MAX_ATTEMPTS = 3;

const LoginPage = () => {
  const navigate = useNavigate();

  // Form state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Security state
  const [attempts, setAttempts] = useState(0);
  const [lockedUntil, setLockedUntil] = useState(null);
  const [countdown, setCountdown] = useState(0);

  // ── Step 1: Redirect if already logged in ──────────────
  useEffect(() => {
    if (isLoggedIn()) {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate]);

  // ── Step 2: Countdown timer for lockout ───────────────
  useEffect(() => {
    if (!lockedUntil) return;
    const interval = setInterval(() => {
      const remaining = Math.ceil((lockedUntil - Date.now()) / 1000);
      if (remaining <= 0) {
        setLockedUntil(null);
        setCountdown(0);
        setAttempts(0);
        setError("");
        clearInterval(interval);
      } else {
        setCountdown(remaining);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [lockedUntil]);

  const isLocked = lockedUntil && Date.now() < lockedUntil;

  // ── Step 3: Input sanitization ────────────────────────
  const sanitize = (value) => value.trim().replace(/[<>'"]/g, "");

  // ── Step 4: Client-side validation ───────────────────
  const validate = () => {
    if (!email || !password) return "Please fill in all fields";
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) return "Please enter a valid email address";
    if (password.length < 6) return "Password must be at least 6 characters";
    return null;
  };

  // ── Step 5: Submit — call API ─────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLocked) return;

    setError("");

    // Validation
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      // ── Step 6: Call POST /api/auth/login ──────────────
      const data = await login(sanitize(email), password);

      // ── Step 7: Save JWT + user info in localStorage ──
      saveSession(data);

      // ── Step 8: Reset attempts on success ─────────────
      setAttempts(0);

      // ── Step 9: Redirect by role ───────────────────────
      navigate("/dashboard", { replace: true });
    } catch (err) {
      // ── Step 10: Handle failed attempt ────────────────
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);

      if (newAttempts >= MAX_ATTEMPTS) {
        // Lock out for 30 seconds
        setLockedUntil(Date.now() + LOCKOUT_DURATION * 1000);
        setError(
          `Too many failed attempts. Please wait ${LOCKOUT_DURATION} seconds.`,
        );
      } else {
        setError(
          `${err.message} — ${MAX_ATTEMPTS - newAttempts} attempt${MAX_ATTEMPTS - newAttempts > 1 ? "s" : ""} remaining`,
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-screen">
      <LeftPanel
        title="Welcome back to your"
        highlight="AI studio"
        desc="Build, test and deploy intelligent agents on your enterprise data — all from one platform."
      />

      <div className="right-panel">
        <form className="form-box" onSubmit={handleSubmit} noValidate>
          <h1 className="form-title">Sign in to AgentFlow</h1>
          <p className="form-sub">
            Enter your credentials to access your workspace
          </p>

          {/* ── Error message ── */}
          {error && (
            <div className="form-error">
              {isLocked
                ? `Account temporarily locked. Try again in ${countdown}s`
                : error}
            </div>
          )}

          {/* ── Lockout warning ── */}
          {attempts > 0 && !isLocked && (
            <div className="form-warning">
              Failed attempt {attempts}/{MAX_ATTEMPTS}
            </div>
          )}

          {/* ── Email ── */}
          <div className="field">
            <label>Email address</label>
            <input
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLocked || loading}
              required
              autoFocus
              autoComplete="email"
              maxLength={254}
            />
          </div>

          {/* ── Password with show/hide ── */}
          <div className="field">
            <label>Password</label>
            <div className="input-icon-wrap">
              <input
                type={showPass ? "text" : "password"}
                placeholder="••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLocked || loading}
                required
                autoComplete="current-password"
                maxLength={128}
              />
              <button
                type="button"
                className="input-icon-btn"
                onClick={() => setShowPass(!showPass)}
                tabIndex={-1}
              >
                <EyeIcon open={showPass} />
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
            disabled={loading || isLocked}
          >
            {loading
              ? "Signing in..."
              : isLocked
                ? `Locked (${countdown}s)`
                : "Sign in"}
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
