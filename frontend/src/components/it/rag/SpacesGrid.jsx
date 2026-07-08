import React, { useState } from "react";
import AccessSelector from "./AccessSelector";
import "../../../styles/it/spacesgrid.css";

/* ── space identity + icons ── */
const monoInitial = (name = "?") => name.trim().charAt(0).toUpperCase() || "?";

const IcDoc = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <path d="M14 3v5h5M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
  </svg>
);
const IcLayers = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
    <path d="M12 2 2 7l10 5 10-5-10-5ZM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
  </svg>
);
const IcArrow = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
    <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IcPlus = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
    <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);
const IcSpaces = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="3" width="7" height="7" rx="1.6" stroke="currentColor" strokeWidth="1.6" />
    <rect x="14" y="3" width="7" height="7" rx="1.6" stroke="currentColor" strokeWidth="1.6" />
    <rect x="3" y="14" width="7" height="7" rx="1.6" stroke="currentColor" strokeWidth="1.6" />
    <rect x="14" y="14" width="7" height="7" rx="1.6" stroke="currentColor" strokeWidth="1.6" />
  </svg>
);

const SpaceCard = ({ s, onClick }) => {
  const status = (s.status || "DRAFT").toLowerCase();
  return (
    <button className="sg-card" onClick={onClick}>
      <div className="sg-card-head">
        <span className="sg-mono">{monoInitial(s.name)}</span>
        <div className="sg-card-titles">
          <div className="sg-card-name">{s.name}</div>
        </div>
        <span className="sg-status-wrap">
          <span className={`sg-status ${status}`}>{s.status || "DRAFT"}</span>
        </span>
      </div>
      <div className="sg-card-desc">{s.description || "No description"}</div>
      <div className="sg-card-foot">
        <span className="sg-stat">
          <IcDoc /> {s.num_documents || 0} docs
        </span>
        <span className="sg-stat">
          <IcLayers /> {s.num_chunks || 0} chunks
        </span>
        <span className="sg-open">
          <IcArrow />
        </span>
      </div>
    </button>
  );
};

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
      <div className="sg-head">
        <div>
          <h1 className="sg-title">RAG Spaces</h1>
          <p className="sg-sub">
            Build and manage retrieval pipelines for your departments
          </p>
        </div>
        <button className="sg-new" onClick={() => setShowCreate(true)}>
          <IcPlus /> New space
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
        {spaces.length === 0 ? (
          <div className="sg-empty">
            <div className="sg-empty-ic">
              <IcSpaces />
            </div>
            <div className="sg-empty-title">No spaces yet</div>
            <div className="sg-empty-sub">
              Create your first RAG space to upload documents, tune the pipeline,
              and let your team query them.
            </div>
            <button className="sg-new" onClick={() => setShowCreate(true)}>
              <IcPlus /> New space
            </button>
          </div>
        ) : (
          depts.map((dept) => {
            const ds = spaces.filter((s) => s.department_id === dept.id);
            if (!ds.length) return null;
            return (
              <section key={dept.id} className="sg-section">
                <div className="sg-section-head">
                  <span className="sg-section-name">{dept.name}</span>
                  <span className="sg-section-count">{ds.length}</span>
                  <span className="sg-section-rule" />
                </div>
                <div className="sg-grid">
                  {ds.map((s) => (
                    <SpaceCard key={s.id} s={s} onClick={() => openSpace(s)} />
                  ))}
                </div>
              </section>
            );
          })
        )}
      </div>
    </div>
  );
};

export default SpacesGrid;
