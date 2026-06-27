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
