import React, { useState, useEffect } from "react";
import {
  listUsers,
  inviteUser,
  deleteUser,
  resendInvite,
  listDepartments,
  createDepartment,
  deleteDepartment,
} from "../../services/usersApi";
import { getUser } from "../../services/authApi";
import "../../styles/admin/users.css";

const UsersPage = () => {
  const [users, setUsers] = useState([]);
  const [depts, setDepts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const currentUser = getUser();

  // null = main view (2 sections), dept object = inside department
  const [activeDept, setActiveDept] = useState(null);

  // Modals
  const [showInvite, setShowInvite] = useState(false);
  const [invEmail, setInvEmail] = useState("");
  const [inviting, setInviting] = useState(false);

  const [showAddDept, setShowAddDept] = useState(false);
  const [newDeptName, setNewDeptName] = useState("");

  // Invite IT modal
  const [showInviteIT, setShowInviteIT] = useState(false);
  const [invITEmail, setInvITEmail] = useState("");
  const [invitingIT, setInvitingIT] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [u, d] = await Promise.all([listUsers(), listDepartments()]);
      setUsers(u);
      setDepts(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Filtered data ──
  const itUsers = users.filter((u) => u.role === "IT");
  const deptUsers = activeDept
    ? users.filter((u) => u.department_id === activeDept.id && u.role !== "IT")
    : [];

  // ── Invite IT ──
  const handleInviteIT = async () => {
    if (!invITEmail.trim()) return;
    setInvitingIT(true);
    setError("");
    setSuccess("");
    try {
      await inviteUser(invITEmail, "IT", null);
      setSuccess(`IT invitation sent to ${invITEmail}`);
      setShowInviteIT(false);
      setInvITEmail("");
      await loadAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setInvitingIT(false);
    }
  };

  // ── Invite User to department ──
  const handleInviteUser = async () => {
    if (!invEmail.trim() || !activeDept) return;
    setInviting(true);
    setError("");
    setSuccess("");
    try {
      await inviteUser(invEmail, "USER", activeDept.id);
      setSuccess(`Invitation sent to ${invEmail}`);
      setShowInvite(false);
      setInvEmail("");
      await loadAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setInviting(false);
    }
  };

  // ── Department actions ──
  const handleAddDept = async () => {
    if (!newDeptName.trim()) return;
    setError("");
    try {
      await createDepartment(newDeptName);
      setNewDeptName("");
      setShowAddDept(false);
      await loadAll();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDeleteDept = async (id, name) => {
    if (!confirm(`Delete department "${name}"? Users will be unassigned.`))
      return;
    try {
      await deleteDepartment(id);
      if (activeDept?.id === id) setActiveDept(null);
      await loadAll();
    } catch (e) {
      setError(e.message);
    }
  };

  // ── User actions ──
  const handleDelete = async (id, name) => {
    if (!confirm(`Remove ${name || "this user"}?`)) return;
    try {
      await deleteUser(id);
      setSuccess("User removed");
      await loadAll();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleResend = async (id, email) => {
    try {
      await resendInvite(id);
      setSuccess(`Invitation resent to ${email}`);
    } catch (e) {
      setError(e.message);
    }
  };

  const statusColors = {
    ACTIVE: { bg: "#ECFDF5", color: "#065F46", border: "#6EE7B7" },
    PENDING: { bg: "#FFF7ED", color: "#92400E", border: "#FCD34D" },
  };

  // ── User row component ──
  const UserRow = ({ u }) => {
    const sc = statusColors[u.status] || statusColors.ACTIVE;
    const isMe = u.id === currentUser?.id;
    const initials = u.name
      ? u.name
          .split(" ")
          .map((n) => n[0])
          .join("")
          .toUpperCase()
          .slice(0, 2)
      : u.email[0].toUpperCase();

    return (
      <tr>
        <td>
          <div className="users-cell-user">
            <div className="users-avatar">{initials}</div>
            <div>
              <div className="users-name">
                {u.name || "—"}{" "}
                {isMe && <span className="users-you">(you)</span>}
              </div>
              <div className="users-email">{u.email}</div>
            </div>
          </div>
        </td>
        <td>
          <span
            className="users-badge"
            style={{
              background: sc.bg,
              color: sc.color,
              border: `1px solid ${sc.border}`,
            }}
          >
            {u.status}
          </span>
        </td>
        <td className="users-date">
          {new Date(u.created_at).toLocaleDateString("en-GB", {
            day: "numeric",
            month: "short",
            year: "numeric",
          })}
        </td>
        <td>
          <div className="users-actions">
            {u.status === "PENDING" && (
              <button
                className="users-action-btn"
                onClick={() => handleResend(u.id, u.email)}
                title="Resend"
              >
                ↻
              </button>
            )}
            {!isMe && u.role !== "ADMIN" && (
              <button
                className="users-action-btn danger"
                onClick={() => handleDelete(u.id, u.name || u.email)}
                title="Remove"
              >
                ✕
              </button>
            )}
          </div>
        </td>
      </tr>
    );
  };

  // ══════════════════════════════════════════════════
  // INSIDE A DEPARTMENT — user list
  // ══════════════════════════════════════════════════
  if (activeDept) {
    return (
      <div className="users-page">
        <div className="users-header">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              className="users-back-btn"
              onClick={() => setActiveDept(null)}
            >
              ←
            </button>
            <div>
              <h1 className="users-title">{activeDept.name}</h1>
              <p className="users-sub">
                {deptUsers.length} member{deptUsers.length !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
          <button
            className="users-invite-btn"
            onClick={() => setShowInvite(true)}
          >
            + Invite to {activeDept.name}
          </button>
        </div>

        {error && (
          <div className="users-error">
            {error}{" "}
            <span
              onClick={() => setError("")}
              style={{ cursor: "pointer", marginLeft: 8 }}
            >
              ✕
            </span>
          </div>
        )}
        {success && (
          <div className="users-success">
            {success}{" "}
            <span
              onClick={() => setSuccess("")}
              style={{ cursor: "pointer", marginLeft: 8 }}
            >
              ✕
            </span>
          </div>
        )}

        <div className="users-table-wrap">
          <table className="users-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Status</th>
                <th>Joined</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {deptUsers.length === 0 && (
                <tr>
                  <td colSpan={4} className="users-empty">
                    No members yet — invite someone!
                  </td>
                </tr>
              )}
              {deptUsers.map((u) => (
                <UserRow key={u.id} u={u} />
              ))}
            </tbody>
          </table>
        </div>

        {/* Invite to department modal */}
        {showInvite && (
          <div className="users-overlay" onClick={() => setShowInvite(false)}>
            <div className="users-modal" onClick={(e) => e.stopPropagation()}>
              <h3 className="users-modal-title">Invite to {activeDept.name}</h3>
              <p className="users-modal-sub">
                This user will be added as End User in the {activeDept.name}{" "}
                department.
              </p>
              <div className="field">
                <label>Email address</label>
                <input
                  type="email"
                  placeholder="colleague@company.com"
                  value={invEmail}
                  onChange={(e) => setInvEmail(e.target.value)}
                  autoFocus
                />
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
                <button
                  className="users-btn-cancel"
                  onClick={() => setShowInvite(false)}
                >
                  Cancel
                </button>
                <button
                  className="users-btn-primary"
                  onClick={handleInviteUser}
                  disabled={inviting || !invEmail.trim()}
                >
                  {inviting ? "Sending..." : "Send invitation"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ══════════════════════════════════════════════════
  // MAIN VIEW — IT section + Department cards
  // ══════════════════════════════════════════════════
  return (
    <div className="users-page">
      <div className="users-header">
        <div>
          <h1 className="users-title">Users</h1>
          <p className="users-sub">
            Manage your IT team and department members
          </p>
        </div>
      </div>

      {error && (
        <div className="users-error">
          {error}{" "}
          <span
            onClick={() => setError("")}
            style={{ cursor: "pointer", marginLeft: 8 }}
          >
            ✕
          </span>
        </div>
      )}
      {success && (
        <div className="users-success">
          {success}{" "}
          <span
            onClick={() => setSuccess("")}
            style={{ cursor: "pointer", marginLeft: 8 }}
          >
            ✕
          </span>
        </div>
      )}

      {loading && <p style={{ color: "#9CA3AF", fontSize: 13 }}>Loading...</p>}

      {!loading && (
        <>
          {/* ── IT SECTION ── */}
          <div className="users-section">
            <div className="users-section-header">
              <div className="users-section-title-row">
                <span className="users-section-icon it">🛠</span>
                <div>
                  <h2 className="users-section-title">IT Team</h2>
                  <p className="users-section-count">
                    {itUsers.length} member{itUsers.length !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>
              <button
                className="users-invite-btn"
                onClick={() => setShowInviteIT(true)}
              >
                + Invite IT
              </button>
            </div>

            <div className="users-table-wrap">
              <table className="users-table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Status</th>
                    <th>Joined</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {itUsers.length === 0 && (
                    <tr>
                      <td colSpan={4} className="users-empty">
                        No IT members yet
                      </td>
                    </tr>
                  )}
                  {itUsers.map((u) => (
                    <UserRow key={u.id} u={u} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── DEPARTMENTS SECTION ── */}
          <div className="users-section" style={{ marginTop: 32 }}>
            <div className="users-section-header">
              <div className="users-section-title-row">
                <span className="users-section-icon dept">👥</span>
                <div>
                  <h2 className="users-section-title">Departments</h2>
                  <p className="users-section-count">
                    Click a department to manage its members
                  </p>
                </div>
              </div>
              <button
                className="users-dept-btn"
                onClick={() => setShowAddDept(true)}
              >
                + Add department
              </button>
            </div>

            <div className="dept-grid">
              {depts.map((d) => {
                const count = users.filter(
                  (u) => u.department_id === d.id && u.role !== "IT",
                ).length;
                return (
                  <div
                    key={d.id}
                    className="dept-card"
                    onClick={() => setActiveDept(d)}
                  >
                    <div className="dept-card-top">
                      <div className="dept-card-icon">👥</div>
                      <button
                        className="dept-card-del"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteDept(d.id, d.name);
                        }}
                      >
                        ✕
                      </button>
                    </div>
                    <div className="dept-card-name">{d.name}</div>
                    <div className="dept-card-count">
                      {count} member{count !== 1 ? "s" : ""}
                    </div>
                  </div>
                );
              })}

              {depts.length === 0 && (
                <div
                  className="dept-empty-card"
                  onClick={() => setShowAddDept(true)}
                >
                  <div style={{ fontSize: 24, marginBottom: 8 }}>+</div>
                  <div
                    style={{ fontSize: 13, fontWeight: 600, color: "#6B7280" }}
                  >
                    Create your first department
                  </div>
                  <div style={{ fontSize: 11, color: "#9CA3AF", marginTop: 4 }}>
                    e.g. Commerce, RH, Finance
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── Invite IT modal ── */}
      {showInviteIT && (
        <div className="users-overlay" onClick={() => setShowInviteIT(false)}>
          <div className="users-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="users-modal-title">Invite IT member</h3>
            <p className="users-modal-sub">
              IT members can create RAG spaces, agents and workflows.
            </p>
            <div className="field">
              <label>Email address</label>
              <input
                type="email"
                placeholder="dev@company.com"
                value={invITEmail}
                onChange={(e) => setInvITEmail(e.target.value)}
                autoFocus
              />
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
              <button
                className="users-btn-cancel"
                onClick={() => setShowInviteIT(false)}
              >
                Cancel
              </button>
              <button
                className="users-btn-primary"
                onClick={handleInviteIT}
                disabled={invitingIT || !invITEmail.trim()}
              >
                {invitingIT ? "Sending..." : "Send invitation"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Add department modal ── */}
      {showAddDept && (
        <div className="users-overlay" onClick={() => setShowAddDept(false)}>
          <div className="users-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="users-modal-title">Create department</h3>
            <p className="users-modal-sub">
              e.g. Commerce, RH, Finance, Marketing...
            </p>
            <div className="field">
              <label>Department name</label>
              <input
                type="text"
                placeholder="Department name"
                value={newDeptName}
                onChange={(e) => setNewDeptName(e.target.value)}
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && handleAddDept()}
              />
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button
                className="users-btn-cancel"
                onClick={() => setShowAddDept(false)}
              >
                Cancel
              </button>
              <button
                className="users-btn-primary"
                onClick={handleAddDept}
                disabled={!newDeptName.trim()}
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UsersPage;
