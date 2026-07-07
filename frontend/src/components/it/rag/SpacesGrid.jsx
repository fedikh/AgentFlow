import React, { useState } from "react";
import AccessSelector from "./AccessSelector";

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
}) => {
  const [showAccess, setShowAccess] = useState(false);

  const closeCreate = () => {
    setShowCreate(false);
    setShowAccess(false);
  };

  return (
    <div className="rag-main">
      <div className="rag-header">
        <div>
          <div className="rag-header-title">RAG Spaces</div>
          <div className="rag-header-desc">
            Build and configure RAG pipelines
          </div>
        </div>
        <button
          className="rag-btn rag-btn-blue"
          onClick={() => setShowCreate(true)}
        >
          + New Space
        </button>
      </div>

      {showCreate && (
        <div
          className="rag-create-overlay"
          onClick={(e) => e.target === e.currentTarget && closeCreate()}
        >
          <div className="rag-create-modal">
            <div className="rag-create-modal-head">
              <span className="rag-create-title">New RAG Space</span>
              <button className="rag-create-x" onClick={closeCreate}>
                ✕
              </button>
            </div>

            <div className="rag-create-body">
              <label className="rag-create-label">Department</label>
              <select
                className="rag-create-input"
                value={createDept}
                onChange={(e) => setCreateDept(e.target.value)}
              >
                <option value="">Select a department…</option>
                {depts.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>

              <label className="rag-create-label">Name</label>
              <input
                className="rag-create-input"
                placeholder="e.g. HR Policy"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />

              <label className="rag-create-label">Description (optional)</label>
              <input
                className="rag-create-input"
                placeholder="What is this space about?"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />

              {/* Access — open to everyone by default; personalize is optional */}
              {createDept && !showAccess && (
                <div className="rag-create-access">
                  <span className="rag-create-access-dot" />
                  <div style={{ flex: 1 }}>
                    <div className="rag-create-access-title">
                      Open to everyone in the department
                    </div>
                    <div className="rag-create-access-sub">
                      All members can use this space by default.
                    </div>
                  </div>
                  <button
                    type="button"
                    className="rag-btn rag-btn-sm"
                    onClick={() => setShowAccess(true)}
                  >
                    Personalize
                  </button>
                </div>
              )}

              {createDept && showAccess && (
                <>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      margin: "16px 0 8px",
                    }}
                  >
                    <label className="rag-create-label" style={{ margin: 0 }}>
                      Personalize access
                    </label>
                    <button
                      type="button"
                      className="rag-btn rag-btn-sm"
                      onClick={() => {
                        setShowAccess(false);
                        setCreateUserIds([]);
                      }}
                    >
                      Reset to everyone
                    </button>
                  </div>
                  <AccessSelector
                    compact
                    users={createDeptUsers}
                    allowedIds={createUserIds}
                    loading={loadingCreateUsers}
                    onChange={setCreateUserIds}
                  />
                </>
              )}
            </div>

            <div className="rag-create-foot">
              <button className="rag-btn" onClick={closeCreate}>
                Cancel
              </button>
              <button
                className="rag-btn rag-btn-blue"
                onClick={handleCreate}
                disabled={!newName.trim() || !createDept}
              >
                Create space
              </button>
            </div>
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
                    <div className="rag-space-card-badge">
                      {s.chunk_strategy}
                    </div>
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
};

export default SpacesGrid;
