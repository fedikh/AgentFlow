import React, { useEffect, useState } from "react";
import {
  fetchMe,
  updateProfile,
  updatePassword,
  updateOrganization,
} from "../../services/authApi";
import "../../styles/shared/profile.css";

const roleBadge = {
  ADMIN: { bg: "#EFF6FF", color: "#1D4ED8" },
  IT: { bg: "#ECFDF5", color: "#065F46" },
  USER: { bg: "#FFF7ED", color: "#92400E" },
};

const initials = (name = "") =>
  name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("") || "?";

const ProfilePage = () => {
  const [user, setUser] = useState(null);

  // modals
  const [editProfileOpen, setEditProfileOpen] = useState(false);
  const [editOrgOpen, setEditOrgOpen] = useState(false);

  // edit profile fields
  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);

  // edit org fields
  const [orgName, setOrgName] = useState("");
  const [savingOrg, setSavingOrg] = useState(false);

  const [msg, setMsg] = useState(null);

  useEffect(() => {
    fetchMe()
      .then((u) => {
        setUser(u);
        setName(u.name || "");
        setOrgName(u.org_name || "");
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (msg) {
      const t = setTimeout(() => setMsg(null), 4000);
      return () => clearTimeout(t);
    }
  }, [msg]);

  if (!user) return <p className="pf-loading">Loading...</p>;

  const rc = roleBadge[user.role] || roleBadge.USER;
  const isAdmin = user.role === "ADMIN";
  const deptNames =
    (user.department_names && user.department_names.length
      ? user.department_names
      : (user.departments || []).map((d) => d.name)) || [];

  const memberSince = new Date(user.created_at).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  // ── handlers ──
  const handleSaveName = async () => {
    const trimmed = name.trim();
    if (!trimmed)
      return setMsg({ type: "error", text: "Name cannot be empty" });
    if (trimmed === user.name)
      return setMsg({ type: "error", text: "Name is unchanged" });
    setSavingName(true);
    try {
      const updated = await updateProfile({ name: trimmed });
      setUser((u) => ({ ...u, name: updated.name }));
      try {
        const stored = JSON.parse(localStorage.getItem("user") || "{}");
        stored.name = updated.name;
        localStorage.setItem("user", JSON.stringify(stored));
      } catch (_) {}
      setMsg({ type: "success", text: "Name updated" });
    } catch (e) {
      setMsg({ type: "error", text: e.message });
    } finally {
      setSavingName(false);
    }
  };

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword)
      return setMsg({ type: "error", text: "Fill in all password fields" });
    if (newPassword.length < 8)
      return setMsg({
        type: "error",
        text: "New password must be at least 8 characters",
      });
    if (newPassword !== confirmPassword)
      return setMsg({ type: "error", text: "New passwords do not match" });
    setSavingPassword(true);
    try {
      await updatePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setMsg({ type: "success", text: "Password changed" });
    } catch (e) {
      setMsg({ type: "error", text: e.message });
    } finally {
      setSavingPassword(false);
    }
  };

  const handleSaveOrg = async () => {
    const trimmed = orgName.trim();
    if (!trimmed)
      return setMsg({
        type: "error",
        text: "Organization name cannot be empty",
      });
    if (trimmed === user.org_name)
      return setMsg({ type: "error", text: "Organization name is unchanged" });
    setSavingOrg(true);
    try {
      const updated = await updateOrganization({ name: trimmed });
      setUser((u) => ({ ...u, org_name: updated.name }));
      setMsg({ type: "success", text: "Organization updated" });
      setEditOrgOpen(false);
    } catch (e) {
      setMsg({ type: "error", text: e.message });
    } finally {
      setSavingOrg(false);
    }
  };

  return (
    <div className="pf-page">
      <div style={{ marginBottom: 20 }}>
        <h1 className="pf-title">My Profile</h1>
        <p className="pf-subtitle">Your account information</p>
      </div>

      {msg && (
        <div className={`pf-banner pf-banner-${msg.type}`}>{msg.text}</div>
      )}

      {/* Avatar header */}
      <div className="pf-header">
        <div className="pf-avatar">{initials(user.name)}</div>
        <div className="pf-header-info">
          <span className="pf-header-name">{user.name}</span>
          <span className="pf-header-email">{user.email}</span>
          <span className="pf-header-role">{user.role}</span>
        </div>
      </div>

      <div className="pf-grid">
        {/* User card */}
        <div className="pf-card">
          <div className="pf-card-head">
            <div className="pf-card-icon">👤</div>
            <span className="pf-card-title">User information</span>
            <button
              className="pf-edit-btn"
              onClick={() => setEditProfileOpen(true)}
            >
              Edit profile
            </button>
          </div>
          <div className="pf-card-body">
            <div className="pf-row">
              <span className="pf-row-label">Full name</span>
              <span className="pf-row-value">{user.name}</span>
            </div>
            <div className="pf-row">
              <span className="pf-row-label">Email</span>
              <span className="pf-row-value">{user.email}</span>
            </div>
            <div className="pf-row">
              <span className="pf-row-label">Member since</span>
              <span className="pf-row-value">{memberSince}</span>
            </div>
            {!isAdmin && deptNames.length > 0 && (
              <div className="pf-row">
                <span className="pf-row-label">
                  {deptNames.length > 1 ? "Departments" : "Department"}
                </span>
                <span className="pf-row-value">{deptNames.join(", ")}</span>
              </div>
            )}
            <div className="pf-row">
              <span className="pf-row-label">Role</span>
              <span
                className="pf-role-badge"
                style={{ background: rc.bg, color: rc.color }}
              >
                {user.role}
              </span>
            </div>
          </div>
        </div>

        {/* Org card */}
        <div className="pf-card">
          <div className="pf-card-head">
            <div className="pf-card-icon pf-card-icon-org">🏢</div>
            <span className="pf-card-title">Organization</span>
            {isAdmin && (
              <button
                className="pf-edit-btn"
                onClick={() => setEditOrgOpen(true)}
              >
                Edit organization
              </button>
            )}
          </div>
          <div className="pf-card-body">
            <div className="pf-org-avatar-row">
              <div className="pf-org-avatar">{initials(user.org_name)}</div>
              <div>
                <div className="pf-org-avatar-name">{user.org_name || "—"}</div>
                <div className="pf-org-avatar-type">{user.org_type || "—"}</div>
              </div>
            </div>
            <div className="pf-row">
              <span className="pf-row-label">Name</span>
              <span className="pf-row-value">{user.org_name || "—"}</span>
            </div>
            <div className="pf-row">
              <span className="pf-row-label">Type</span>
              <span className="pf-row-value">{user.org_type || "—"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ════ EDIT PROFILE MODAL ════ */}
      {editProfileOpen && (
        <div
          className="pf-modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) setEditProfileOpen(false);
          }}
        >
          <div className="pf-modal">
            <div className="pf-modal-head">
              <span className="pf-modal-title">Edit profile</span>
              <button
                className="pf-modal-close"
                onClick={() => setEditProfileOpen(false)}
              >
                ✕
              </button>
            </div>
            <div className="pf-modal-body">
              {/* Name */}
              <div>
                <label className="pf-field-label">Full name</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    className="pf-input"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                  />
                  <button
                    className="pf-btn"
                    onClick={handleSaveName}
                    disabled={savingName}
                  >
                    {savingName ? "Saving…" : "Save"}
                  </button>
                </div>
              </div>

              <div className="pf-divider" />

              {/* Password */}
              <div className="pf-pw-group">
                <span className="pf-section-title">Change password</span>
                <div>
                  <label className="pf-field-label">Current password</label>
                  <input
                    type="password"
                    className="pf-input"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="••••••••"
                  />
                </div>
                <div>
                  <label className="pf-field-label">New password</label>
                  <input
                    type="password"
                    className="pf-input"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="At least 8 characters"
                  />
                </div>
                <div>
                  <label className="pf-field-label">Confirm new password</label>
                  <input
                    type="password"
                    className="pf-input"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat new password"
                  />
                </div>
                <button
                  className="pf-btn pf-btn-full"
                  onClick={handleChangePassword}
                  disabled={savingPassword}
                >
                  {savingPassword ? "Updating…" : "Update password"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ════ EDIT ORGANIZATION MODAL (ADMIN) ════ */}
      {editOrgOpen && isAdmin && (
        <div
          className="pf-modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) setEditOrgOpen(false);
          }}
        >
          <div className="pf-modal">
            <div className="pf-modal-head">
              <span className="pf-modal-title">Edit organization</span>
              <button
                className="pf-modal-close"
                onClick={() => setEditOrgOpen(false)}
              >
                ✕
              </button>
            </div>
            <div className="pf-modal-body">
              <div>
                <label className="pf-field-label">Organization name</label>
                <input
                  className="pf-input"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="Organization name"
                />
              </div>
              <button
                className="pf-btn pf-btn-full"
                onClick={handleSaveOrg}
                disabled={savingOrg}
              >
                {savingOrg ? "Saving…" : "Save organization"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfilePage;
