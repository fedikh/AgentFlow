import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import "../../styles/auth/auth.css";
import LeftPanel from "../../components/auth/LeftPanel";
import {
  forgotPassword,
  verifyOtp,
  resetPassword,
} from "../../services/authApi";

const StepDot = ({ n, current }) => (
  <div
    className={`step-dot ${n < current ? "done" : n === current ? "active" : ""}`}
  />
);

const ForgotPasswordPage = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [newPass, setNew] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // ── OTP input helpers ──
  const handleOtp = (val, i) => {
    const next = [...otp];
    next[i] = val.slice(-1);
    setOtp(next);
    if (val && i < 5) document.getElementById(`otp-${i + 1}`)?.focus();
  };

  const handleOtpBack = (e, i) => {
    if (e.key === "Backspace" && !otp[i] && i > 0)
      document.getElementById(`otp-${i - 1}`)?.focus();
  };

  // ── Step 1 — Send OTP ──
  const handleSendCode = async () => {
    setError("");
    setLoading(true);
    try {
      await forgotPassword(email);
      setSuccess("Reset code sent! Check your inbox.");
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Step 2 — Verify OTP ──
  const handleVerifyOtp = async () => {
    setError("");
    setLoading(true);
    try {
      await verifyOtp(email, otp.join(""));
      setSuccess("");
      setStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Step 3 — Reset password ──
  const handleReset = async () => {
    setError("");
    if (newPass !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (newPass.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await resetPassword(email, otp.join(""), newPass);
      setSuccess("Password reset successfully!");
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-screen">
      <LeftPanel
        title="Reset your"
        highlight="password"
        desc="Enter your email, receive a 6-digit code, and set a new password."
      />

      <div className="right-panel">
        <div className="form-box">
          <div className="step-indicator">
            <StepDot n={1} current={step} />
            <StepDot n={2} current={step} />
            <StepDot n={3} current={step} />
          </div>

          {error && <div className="form-error">{error}</div>}
          {success && <div className="form-success">{success}</div>}

          {/* ── Step 1 — Email ── */}
          {step === 1 && (
            <div>
              <h1 className="form-title">Forgot your password?</h1>
              <p className="form-sub">
                Enter the email associated with your AgentFlow account.
              </p>
              <div className="field">
                <label>Email address</label>
                <input
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoFocus
                />
              </div>
              <button
                className="btn-primary"
                onClick={handleSendCode}
                disabled={loading || !email}
              >
                {loading ? "Sending..." : "Send reset code"}
              </button>
              <p className="form-footer">
                <span className="link" onClick={() => navigate("/login")}>
                  ← Back to login
                </span>
              </p>
            </div>
          )}

          {/* ── Step 2 — OTP ── */}
          {step === 2 && (
            <div>
              <h1 className="form-title">Check your inbox</h1>
              <p className="form-sub">
                We sent a 6-digit code to <strong>{email}</strong>.
              </p>
              <div className="otp-row">
                {otp.map((val, i) => (
                  <input
                    key={i}
                    id={`otp-${i}`}
                    className="otp-input"
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={val}
                    onChange={(e) => handleOtp(e.target.value, i)}
                    onKeyDown={(e) => handleOtpBack(e, i)}
                    autoFocus={i === 0}
                  />
                ))}
              </div>
              <button
                className="btn-primary"
                onClick={handleVerifyOtp}
                disabled={loading || otp.join("").length < 6}
              >
                {loading ? "Verifying..." : "Verify code"}
              </button>
              <p className="form-footer">
                Didn't receive it?{" "}
                <span
                  className="link"
                  onClick={() => {
                    setStep(1);
                    setOtp(["", "", "", "", "", ""]);
                  }}
                >
                  Resend code
                </span>
              </p>
            </div>
          )}

          {/* ── Step 3 — New password ── */}
          {step === 3 && (
            <div>
              <h1 className="form-title">Set a new password</h1>
              <p className="form-sub">
                Choose a strong password for your account.
              </p>
              <div className="field">
                <label>New password</label>
                <input
                  type="password"
                  placeholder="Min. 8 characters"
                  value={newPass}
                  onChange={(e) => setNew(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="field">
                <label>Confirm password</label>
                <input
                  type="password"
                  placeholder="Repeat your password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </div>
              <button
                className="btn-primary"
                onClick={handleReset}
                disabled={loading}
              >
                {loading ? "Resetting..." : "Reset password"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
