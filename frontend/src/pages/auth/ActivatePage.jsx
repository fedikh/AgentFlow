import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import "../../styles/auth/auth.css";
import LeftPanel from "../../components/auth/LeftPanel";
import { activateUser } from "../../services/usersApi";

const ActivatePage = () => {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";

  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [role, setRole] = useState("");

  const handleActivate = async (e) => {
    e.preventDefault();
    setError("");

    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (!token) {
      setError("Invalid activation link");
      return;
    }

    setLoading(true);
    try {
      const res = await activateUser(token, name, password);
      setSuccess(true);
      setRole(res.role || "");
      // Always redirect to /login — never to /admin
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-screen">
      <LeftPanel
        title="Activate your"
        highlight="account"
        desc="Set your name and password to join your team on AgentFlow."
      />

      <div className="right-panel">
        <form className="form-box" onSubmit={handleActivate}>
          <h1 className="form-title">Activate your account</h1>
          <p className="form-sub">
            You've been invited to join an AgentFlow organization.
          </p>

          {error && <div className="form-error">{error}</div>}
          {success && (
            <div className="form-success">
              Account activated as <strong>{role}</strong>! Redirecting to
              login...
            </div>
          )}

          {!success && (
            <>
              <div className="field">
                <label>Full name</label>
                <input
                  type="text"
                  placeholder="Your full name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  autoFocus
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
              <div className="field">
                <label>Confirm password</label>
                <input
                  type="password"
                  placeholder="Repeat your password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                />
              </div>
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? "Activating..." : "Activate account"}
              </button>
            </>
          )}
        </form>
      </div>
    </div>
  );
};

export default ActivatePage;
