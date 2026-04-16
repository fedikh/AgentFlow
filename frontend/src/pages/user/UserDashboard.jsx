import { useNavigate } from "react-router-dom";
import { getUser } from "../../services/authApi";

const UserDashboard = () => {
  const user = getUser();
  const navigate = useNavigate();

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
        Welcome, <strong>{user?.name}</strong>
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "14px",
        }}
      >
        <div
          onClick={() => navigate("/user/chat")}
          style={{
            background: "#fff",
            border: "1px solid #E5E7EB",
            borderRadius: "10px",
            padding: "24px",
            cursor: "pointer",
            transition: "border-color 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#2563EB")}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#E5E7EB")}
        >
          <div style={{ fontSize: "22px", marginBottom: "10px" }}>💬</div>
          <div
            style={{ fontSize: "14px", fontWeight: "700", color: "#111827" }}
          >
            Start chatting
          </div>
          <div style={{ fontSize: "12px", color: "#6B7280", marginTop: "4px" }}>
            Use an AI agent
          </div>
        </div>

        <div
          onClick={() => navigate("/user/history")}
          style={{
            background: "#fff",
            border: "1px solid #E5E7EB",
            borderRadius: "10px",
            padding: "24px",
            cursor: "pointer",
            transition: "border-color 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#2563EB")}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#E5E7EB")}
        >
          <div style={{ fontSize: "22px", marginBottom: "10px" }}>🕐</div>
          <div
            style={{ fontSize: "14px", fontWeight: "700", color: "#111827" }}
          >
            View history
          </div>
          <div style={{ fontSize: "12px", color: "#6B7280", marginTop: "4px" }}>
            Past conversations
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserDashboard;
