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

/* ── Clean line icons (no emoji) ── */
const I = {
  team: (p) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="9" cy="7" r="3.2" stroke="currentColor" strokeWidth="1.8" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13A4 4 0 0 1 16 11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  dept: (p) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M3 21V7l6-3 6 3v14M15 21V11l6 3v7M3 21h18M7 9v0M7 13v0M7 17v0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  eye: (p) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="12" cy="12" r="2.6" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  ),
  edit: (p) => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  resend: (p) => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  close: (p) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M18 6 6 18M6 6l12 12" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  ),
  back: (p) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M15 18l-6-6 6-6" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  plus: (p) => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  ),
};

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

  // ── Department checkbox list component ──
  const DeptCheckboxList = ({ selected, setSelected, label }) => (
    <div className="field" style={{ marginTop: 12 }}>
      <label>{label}</label>
      <div className="users-checklist">
        {depts.length === 0 && (
          <span className="users-checklist-empty">
            No departments yet — create one first
          </span>
        )}
        {depts.map((d) => (
          <label
            key={d.id}
            className={`users-checkitem ${selected.includes(d.id) ? "on" : ""}`}
          >
            <input
              type="checkbox"
              checked={selected.includes(d.id)}
              onChange={() => toggleDept(d.id, setSelected)}
            />
            <span>{d.name}</span>
          </label>
        ))}
      </div>
      {selected.length === 0 && (
        <span className="users-check-warn">Select at least one department</span>
      )}
    </div>
  );

  // ── User row component (enhanced) ──
  const UserRow = ({ u, showRole, showEditDepts }) => {
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
                <div className="users-deptchips">
                  {u.department_names.map((name, i) => (
                    <span key={i} className="users-deptchip">
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
            <span className={`users-badge role-${(u.role || "user").toLowerCase()}`}>
              {u.role}
            </span>
          </td>
        )}
        <td>
          <span
            className={`users-badge status-${(u.status || "active").toLowerCase()}`}
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
              >
                <I.edit />
              </button>
            )}
            {u.status === "PENDING" && (
              <button
                className="users-action-btn"
                onClick={() => handleResend(u.id, u.email)}
                title="Resend invitation"
              >
                <I.resend />
              </button>
            )}
            {!isMe && u.role !== "ADMIN" && (
              <button
                className="users-action-btn danger"
                onClick={() => handleDelete(u.id, u.name || u.email)}
                title="Remove"
              >
                <I.close />
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
          <span>{error}</span>
          <span
            onClick={() => setError("")}
            style={{ cursor: "pointer", display: "inline-flex" }}
          >
            <I.close />
          </span>
        </div>
      )}
      {success && (
        <div className="users-success">
          <span>{success}</span>
          <span
            onClick={() => setSuccess("")}
            style={{ cursor: "pointer", display: "inline-flex" }}
          >
            <I.close />
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
          <div className="users-checklist" style={{ maxHeight: 220 }}>
            {depts.map((d) => (
              <label
                key={d.id}
                className={`users-checkitem ${editDepts.includes(d.id) ? "on" : ""}`}
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
                />
                <span>{d.name}</span>
              </label>
            ))}
          </div>
          {editDepts.length === 0 && (
            <span className="users-check-warn">
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
              <I.back />
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
              <I.back />
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
            <I.plus /> Invite to {activeDept.name}
          </button>
        </div>

        <Banners />

        {/* IT members in this department */}
        {deptIT.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <div className="users-eyebrow">
              <I.team width={13} height={13} /> IT members ({deptIT.length})
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
          <div className="users-eyebrow">
            <I.dept width={13} height={13} /> End users ({deptUsers.length})
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
                <div className="users-rolepick">
                  {["USER", "IT"].map((r) => (
                    <button
                      key={r}
                      className={`users-rolepick-btn ${invRole === r ? "on" : ""}`}
                      onClick={() => setInvRole(r)}
                    >
                      {r === "USER" ? "End User" : "IT"}
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
          className="users-dept-btn"
          onClick={() => setActiveView("all")}
        >
          <I.eye /> View all users ({users.length})
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
                <span className="users-section-icon it">
                  <I.team />
                </span>
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
                <I.plus /> Invite IT
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
                <span className="users-section-icon dept">
                  <I.dept />
                </span>
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
                <I.plus /> Add department
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
                      <div className="dept-card-icon">
                        <I.dept />
                      </div>
                      <button
                        className="dept-card-del"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteDept(d.id, d.name);
                        }}
                      >
                        <I.close />
                      </button>
                    </div>
                    <div className="dept-card-name">{d.name}</div>
                    <div className="dept-card-count">
                      {totalCount} member{totalCount !== 1 ? "s" : ""}
                    </div>
                    {(itCount > 0 || userCount > 0) && (
                      <div className="dept-card-breakdown">
                        {itCount > 0 && (
                          <span className="dept-card-stat">{itCount} IT</span>
                        )}
                        {userCount > 0 && (
                          <span className="dept-card-stat">
                            {userCount} User{userCount !== 1 ? "s" : ""}
                          </span>
                        )}
                      </div>
                    )}
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
