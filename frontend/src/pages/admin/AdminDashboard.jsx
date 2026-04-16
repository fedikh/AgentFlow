import { getUser } from "../../services/authApi";

const AdminDashboard = () => {
  const user = getUser();

  return (
    <div>
      <h1
        style={{
          fontSize: "20px",
          fontWeight: "800",
          color: "#111827",
          letterSpacing: "-0.3px",
          margin: "0 0 4px",
        }}
      >
        Dashboard
      </h1>
      <p style={{ fontSize: "13px", color: "#6B7280", marginBottom: "24px" }}>
        Welcome back, <strong>{user?.name}</strong> — {user?.org_name}
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "14px",
          marginBottom: "24px",
        }}
      >
        {[
          { label: "Total Users", value: "—" },
          { label: "Active Agents", value: "—" },
          { label: "RAG Spaces", value: "—" },
          { label: "Workflows", value: "—" },
        ].map((s) => (
          <div
            key={s.label}
            style={{
              background: "#fff",
              border: "1px solid #E5E7EB",
              borderRadius: "10px",
              padding: "18px 20px",
            }}
          >
            <div
              style={{
                fontSize: "12px",
                color: "#6B7280",
                fontWeight: "500",
                marginBottom: "8px",
              }}
            >
              {s.label}
            </div>
            <div
              style={{ fontSize: "26px", fontWeight: "800", color: "#111827" }}
            >
              {s.value}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          background: "#fff",
          border: "1px solid #E5E7EB",
          borderRadius: "10px",
          padding: "28px",
          textAlign: "center",
        }}
      >
        <p style={{ color: "#9CA3AF", fontSize: "13px" }}>
          Connect to API to load data
        </p>
      </div>
    </div>
  );
};

export default AdminDashboard;
