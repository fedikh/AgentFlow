import React, { useState, useEffect } from "react";
import {
  listUsers,
  inviteUser,
  updateUser,
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

  // Views: null = main, "dept" = inside department, "all" = all users
  const [activeDept, setActiveDept] = useState(null);
  const [activeView, setActiveView] = useState(null); // null | "all"

  // Modals
  const [showInvite, setShowInvite] = useState(false);
  const [invEmail, setInvEmail] = useState("");
  const [invRole, setInvRole] = useState("USER");
  const [inviting, setInviting] = useState(false);
  const [invSelectedDepts, setInvSelectedDepts] = useState([]);

  const [showAddDept, setShowAddDept] = useState(false);
  const [newDeptName, setNewDeptName] = useState("");

  // Invite IT modal
  const [showInviteIT, setShowInviteIT] = useState(false);
  const [invITEmail, setInvITEmail] = useState("");
  const [invitingIT, setInvitingIT] = useState(false);
  const [invITSelectedDepts, setInvITSelectedDepts] = useState([]);

  // Edit IT departments modal
  const [editUser, setEditUser] = useState(null);
  const [editDepts, setEditDepts] = useState([]);
  const [saving, setSaving] = useState(false);

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
  const allNonAdmin = users.filter((u) => u.role !== "ADMIN");

  // Department members: IT + Users who have this dept
  const deptMembers = activeDept
    ? users.filter(
        (u) =>
          u.department_ids &&
          u.department_ids.includes(activeDept.id) &&
          u.role !== "ADMIN",
      )
    : [];

  const deptIT = deptMembers.filter((u) => u.role === "IT");
  const deptUsers = deptMembers.filter((u) => u.role === "USER");

  // ── Toggle department selection ──
  const toggleDept = (deptId, setList) => {
    setList((prev) =>
      prev.includes(deptId)
        ? prev.filter((id) => id !== deptId)
        : [...prev, deptId],
    );
  };

  // ── Invite IT ──
  const handleInviteIT = async () => {
    if (!invITEmail.trim() || invITSelectedDepts.length === 0) return;
    setInvitingIT(true);
    setError("");
    setSuccess("");
    try {
      await inviteUser(invITEmail, "IT", invITSelectedDepts);
      setSuccess(`IT invitation sent to ${invITEmail}`);
      setShowInviteIT(false);
      setInvITEmail("");
      setInvITSelectedDepts([]);
      await loadAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setInvitingIT(false);
    }
  };

  // ── Invite User ──
  const handleInviteUser = async () => {
    if (!invEmail.trim() || invSelectedDepts.length === 0) return;
    setInviting(true);
    setError("");
    setSuccess("");
    try {
      await inviteUser(invEmail, invRole, invSelectedDepts);
      setSuccess(`Invitation sent to ${invEmail}`);
      setShowInvite(false);
      setInvEmail("");
      setInvSelectedDepts([]);
      setInvRole("USER");
      await loadAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setInviting(false);
    }
  };

  // ── Edit user departments (add/remove) ──
  const handleOpenEditDepts = (u) => {
    setEditUser(u);
    setEditDepts(u.department_ids || []);
  };

  const handleSaveEditDepts = async () => {
    if (!editUser) return;
    setSaving(true);
    setError("");
    try {
      await updateUser(editUser.id, { department_ids: editDepts });
      setSuccess(`Departments updated for ${editUser.name || editUser.email}`);
      setEditUser(null);
      await loadAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
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

  const roleColors = {
    ADMIN: { bg: "#FEF2F2", color: "#991B1B", border: "#FECACA" },
    IT: { bg: "#EFF6FF", color: "#1E40AF", border: "#BFDBFE" },
    USER: { bg: "#F0FDF4", color: "#166534", border: "#BBF7D0" },
  };

  // ── Department checkbox list component ──
  const DeptCheckboxList = ({ selected, setSelected, label }) => (
    <div className="field" style={{ marginTop: 12 }}>
      <label>{label}</label>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6,
          marginTop: 6,
          padding: "10px 12px",
          background: "#F9FAFB",
          borderRadius: 8,
          border: "1px solid #E5E7EB",
          maxHeight: 180,
          overflowY: "auto",
        }}
      >
        {depts.length === 0 && (
          <span style={{ fontSize: 12, color: "#9CA3AF" }}>
            No departments yet — create one first
          </span>
        )}
        {depts.map((d) => (
          <label
            key={d.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 13,
              cursor: "pointer",
              padding: "4px 0",
            }}
          >
            <input
              type="checkbox"
              checked={selected.includes(d.id)}
              onChange={() => toggleDept(d.id, setSelected)}
              style={{ accentColor: "#2563EB", width: 16, height: 16 }}
            />
            <span style={{ color: "#1F2937" }}>{d.name}</span>
          </label>
        ))}
      </div>
      {selected.length === 0 && (
        <span
          style={{
            fontSize: 11,
            color: "#DC2626",
            marginTop: 4,
            display: "block",
          }}
        >
          Select at least one department
        </span>
      )}
    </div>
  );

  // ── User row component (enhanced) ──
  const UserRow = ({ u, showRole, showEditDepts }) => {
    const sc = statusColors[u.status] || statusColors.ACTIVE;
    const rc = roleColors[u.role] || roleColors.USER;
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
              {u.department_names && u.department_names.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    gap: 4,
                    flexWrap: "wrap",
                    marginTop: 3,
                  }}
                >
                  {u.department_names.map((name, i) => (
                    <span
                      key={i}
                      style={{
                        fontSize: 10,
                        fontWeight: 500,
                        padding: "1px 6px",
                        borderRadius: 4,
                        background: "#EFF6FF",
                        color: "#1D4ED8",
                        border: "1px solid #BFDBFE",
                      }}
                    >
                      {name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </td>
        {showRole && (
          <td>
            <span
              className="users-badge"
              style={{
                background: rc.bg,
                color: rc.color,
                border: `1px solid ${rc.border}`,
              }}
            >
              {u.role}
            </span>
          </td>
        )}
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
            {showEditDepts && !isMe && u.role !== "ADMIN" && (
              <button
                className="users-action-btn"
                onClick={() => handleOpenEditDepts(u)}
                title="Edit departments"
                style={{ fontSize: 13 }}
              >
                ✎
              </button>
            )}
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

  // ── Error/Success banners ──
  const Banners = () => (
    <>
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
    </>
  );

  // ── Edit departments modal (shared) ──
  const EditDeptsModal = () => {
    if (!editUser) return null;
    return (
      <div className="users-overlay" onClick={() => setEditUser(null)}>
        <div className="users-modal" onClick={(e) => e.stopPropagation()}>
          <h3 className="users-modal-title">
            Edit departments — {editUser.name || editUser.email}
          </h3>
          <p className="users-modal-sub">
            {editUser.role === "IT"
              ? "Select the departments this IT member can build RAG for."
              : "Select the departments this user can access."}
          </p>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              marginTop: 12,
              padding: "10px 12px",
              background: "#F9FAFB",
              borderRadius: 8,
              border: "1px solid #E5E7EB",
              maxHeight: 220,
              overflowY: "auto",
            }}
          >
            {depts.map((d) => (
              <label
                key={d.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 13,
                  cursor: "pointer",
                  padding: "6px 4px",
                  borderRadius: 6,
                  background: editDepts.includes(d.id)
                    ? "#EFF6FF"
                    : "transparent",
                }}
              >
                <input
                  type="checkbox"
                  checked={editDepts.includes(d.id)}
                  onChange={() =>
                    setEditDepts((prev) =>
                      prev.includes(d.id)
                        ? prev.filter((id) => id !== d.id)
                        : [...prev, d.id],
                    )
                  }
                  style={{ accentColor: "#2563EB", width: 16, height: 16 }}
                />
                <span
                  style={{
                    color: "#1F2937",
                    fontWeight: editDepts.includes(d.id) ? 500 : 400,
                  }}
                >
                  {d.name}
                </span>
              </label>
            ))}
          </div>
          {editDepts.length === 0 && (
            <span
              style={{
                fontSize: 11,
                color: "#DC2626",
                marginTop: 6,
                display: "block",
              }}
            >
              At least one department is required
            </span>
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
            <button
              className="users-btn-cancel"
              onClick={() => setEditUser(null)}
            >
              Cancel
            </button>
            <button
              className="users-btn-primary"
              onClick={handleSaveEditDepts}
              disabled={saving || editDepts.length === 0}
            >
              {saving ? "Saving..." : "Save changes"}
            </button>
          </div>
        </div>
      </div>
    );
  };

  // ══════════════════════════════════════════════════
  // VIEW: ALL USERS
  // ══════════════════════════════════════════════════
  if (activeView === "all") {
    return (
      <div className="users-page">
        <div className="users-header">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              className="users-back-btn"
              onClick={() => setActiveView(null)}
            >
              ←
            </button>
            <div>
              <h1 className="users-title">All Users</h1>
              <p className="users-sub">
                {users.length} total user{users.length !== 1 ? "s" : ""} in your
                organization
              </p>
            </div>
          </div>
        </div>

        <Banners />

        <div className="users-table-wrap">
          <table className="users-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Joined</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <UserRow key={u.id} u={u} showRole showEditDepts />
              ))}
            </tbody>
          </table>
        </div>

        <EditDeptsModal />
      </div>
    );
  }

  // ══════════════════════════════════════════════════
  // VIEW: INSIDE A DEPARTMENT
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
                {deptMembers.length} member{deptMembers.length !== 1 ? "s" : ""}{" "}
                — {deptIT.length} IT, {deptUsers.length} User
                {deptUsers.length !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
          <button
            className="users-invite-btn"
            onClick={() => {
              setInvSelectedDepts([activeDept.id]);
              setShowInvite(true);
            }}
          >
            + Invite to {activeDept.name}
          </button>
        </div>

        <Banners />

        {/* IT members in this department */}
        {deptIT.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: "#6B7280",
                marginBottom: 8,
                textTransform: "uppercase",
                letterSpacing: "0.5px",
              }}
            >
              🛠 IT members ({deptIT.length})
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
                  {deptIT.map((u) => (
                    <UserRow key={u.id} u={u} showEditDepts />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* End Users in this department */}
        <div>
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "#6B7280",
              marginBottom: 8,
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            👤 End users ({deptUsers.length})
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
                {deptUsers.length === 0 && (
                  <tr>
                    <td colSpan={4} className="users-empty">
                      No end users yet — invite someone!
                    </td>
                  </tr>
                )}
                {deptUsers.map((u) => (
                  <UserRow key={u.id} u={u} showEditDepts />
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Invite modal — with role choice + multi-dept */}
        {showInvite && (
          <div className="users-overlay" onClick={() => setShowInvite(false)}>
            <div className="users-modal" onClick={(e) => e.stopPropagation()}>
              <h3 className="users-modal-title">Invite to {activeDept.name}</h3>
              <p className="users-modal-sub">
                Choose the role and departments for this user.
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
              <div className="field" style={{ marginTop: 12 }}>
                <label>Role</label>
                <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                  {["USER", "IT"].map((r) => (
                    <button
                      key={r}
                      onClick={() => setInvRole(r)}
                      style={{
                        flex: 1,
                        padding: "8px 12px",
                        borderRadius: 8,
                        border:
                          invRole === r
                            ? "2px solid #2563EB"
                            : "1px solid #E5E7EB",
                        background: invRole === r ? "#EFF6FF" : "#fff",
                        color: invRole === r ? "#1D4ED8" : "#6B7280",
                        fontWeight: invRole === r ? 600 : 400,
                        fontSize: 13,
                        cursor: "pointer",
                      }}
                    >
                      {r === "USER" ? "👤 End User" : "🛠 IT"}
                    </button>
                  ))}
                </div>
              </div>
              <DeptCheckboxList
                selected={invSelectedDepts}
                setSelected={setInvSelectedDepts}
                label="Departments"
              />
              <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
                <button
                  className="users-btn-cancel"
                  onClick={() => {
                    setShowInvite(false);
                    setInvSelectedDepts([]);
                    setInvRole("USER");
                  }}
                >
                  Cancel
                </button>
                <button
                  className="users-btn-primary"
                  onClick={handleInviteUser}
                  disabled={
                    inviting ||
                    !invEmail.trim() ||
                    invSelectedDepts.length === 0
                  }
                >
                  {inviting ? "Sending..." : "Send invitation"}
                </button>
              </div>
            </div>
          </div>
        )}

        <EditDeptsModal />
      </div>
    );
  }

  // ══════════════════════════════════════════════════
  // MAIN VIEW — IT section + Departments + All Users button
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
        <button
          className="users-invite-btn"
          onClick={() => setActiveView("all")}
          style={{
            background: "#F3F4F6",
            color: "#374151",
            border: "1px solid #E5E7EB",
          }}
        >
          👁 View all users ({users.length})
        </button>
      </div>

      <Banners />

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
                    <UserRow key={u.id} u={u} showEditDepts />
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
                const totalCount = users.filter(
                  (u) =>
                    u.department_ids &&
                    u.department_ids.includes(d.id) &&
                    u.role !== "ADMIN",
                ).length;
                const itCount = users.filter(
                  (u) =>
                    u.department_ids &&
                    u.department_ids.includes(d.id) &&
                    u.role === "IT",
                ).length;
                const userCount = totalCount - itCount;
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
                      {totalCount} member{totalCount !== 1 ? "s" : ""}
                    </div>
                    <div
                      style={{ fontSize: 11, color: "#9CA3AF", marginTop: 2 }}
                    >
                      {itCount > 0 && <span>{itCount} IT</span>}
                      {itCount > 0 && userCount > 0 && <span> · </span>}
                      {userCount > 0 && (
                        <span>
                          {userCount} User{userCount !== 1 ? "s" : ""}
                        </span>
                      )}
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
              IT members can create RAG spaces, agents and workflows. Select the
              departments they will work on.
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
            <DeptCheckboxList
              selected={invITSelectedDepts}
              setSelected={setInvITSelectedDepts}
              label="Assign to departments"
            />
            <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
              <button
                className="users-btn-cancel"
                onClick={() => {
                  setShowInviteIT(false);
                  setInvITSelectedDepts([]);
                }}
              >
                Cancel
              </button>
              <button
                className="users-btn-primary"
                onClick={handleInviteIT}
                disabled={
                  invitingIT ||
                  !invITEmail.trim() ||
                  invITSelectedDepts.length === 0
                }
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

      <EditDeptsModal />
    </div>
  );
};

export default UsersPage;
