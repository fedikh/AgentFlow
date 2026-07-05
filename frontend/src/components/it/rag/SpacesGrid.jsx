import React from "react";

const SpacesGrid = ({
  depts,
  spaces,
  openSpace,
  showCreate,
  setShowCreate,
  createDept,
  setCreateDept,
  newName,
  setNewName,
  newDesc,
  setNewDesc,
  handleCreate,
  createDeptUsers = [],
  loadingCreateUsers = false,
  createUserIds = [],
  setCreateUserIds = () => {},
}) => (
  <div className="rag-main">
    <div className="rag-header">
      <div>
        <div className="rag-header-title">RAG Spaces</div>
        <div className="rag-header-desc">Build and configure RAG pipelines</div>
      </div>
      <button
        className="rag-btn rag-btn-blue"
        onClick={() => setShowCreate(true)}
      >
        + New Space
      </button>
    </div>

    {showCreate && (
      <div className="rag-create-card" style={{ maxWidth: 400 }}>
        <div className="rag-create-title">New Space</div>
        <div className="rag-create-label">Department</div>
        <select
          className="rag-create-input"
          value={createDept}
          onChange={(e) => setCreateDept(e.target.value)}
        >
          <option value="">Select…</option>
          {depts.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <input
          className="rag-create-input"
          placeholder="Space name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <input
          className="rag-create-input"
          placeholder="Description (optional)"
          value={newDesc}
          onChange={(e) => setNewDesc(e.target.value)}
        />

        {/* Access control (Batch 1) — who can use this space */}
        {createDept && (
          <>
            <div className="rag-create-label">Who can use this space</div>
            <div
              style={{
                border: "1px solid var(--rag-border, #e2e8f0)",
                borderRadius: 8,
                padding: 8,
                maxHeight: 160,
                overflowY: "auto",
                marginBottom: 8,
              }}
            >
              {loadingCreateUsers && (
                <div className="rag-create-label">Loading…</div>
              )}
              {!loadingCreateUsers && createDeptUsers.length === 0 && (
                <div className="rag-create-label">
                  No end-users in this department — leave empty and everyone in
                  the department will have access.
                </div>
              )}
              {!loadingCreateUsers &&
                createDeptUsers.map((u) => (
                  <label
                    key={u.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "4px 2px",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={createUserIds.includes(u.id)}
                      onChange={() =>
                        setCreateUserIds(
                          createUserIds.includes(u.id)
                            ? createUserIds.filter((x) => x !== u.id)
                            : [...createUserIds, u.id],
                        )
                      }
                    />
                    <span>{u.name || u.email}</span>
                  </label>
                ))}
            </div>
            <div
              className="rag-create-label"
              style={{ marginTop: -4, marginBottom: 8, opacity: 0.7 }}
            >
              {createUserIds.length === 0
                ? "Empty = all department users can access (default)."
                : `${createUserIds.length} user(s) selected.`}
            </div>
          </>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
          <button className="rag-btn rag-btn-blue" onClick={handleCreate}>
            Create
          </button>
          <button className="rag-btn" onClick={() => setShowCreate(false)}>
            Cancel
          </button>
        </div>
      </div>
    )}

    <div className="rag-grid">
      {depts.map((dept) => {
        const ds = spaces.filter((s) => s.department_id === dept.id);
        if (!ds.length) return null;
        return (
          <div key={dept.id} className="rag-dept-section">
            <div className="rag-dept-label">{dept.name}</div>
            <div className="rag-cards">
              {ds.map((s) => (
                <div
                  key={s.id}
                  className="rag-space-card"
                  onClick={() => openSpace(s)}
                >
                  <div className="rag-space-card-badge">{s.chunk_strategy}</div>
                  <div className="rag-space-card-name">{s.name}</div>
                  <div className="rag-space-card-desc">
                    {s.description || "No description"}
                  </div>
                  <div className="rag-space-card-footer">
                    <span>📄 {s.num_documents || 0} docs</span>
                    <span>🧩 {s.num_chunks || 0} chunks</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
      {spaces.length === 0 && (
        <div className="rag-empty-state">No spaces yet</div>
      )}
    </div>
  </div>
);

export default SpacesGrid;
