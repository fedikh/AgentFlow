import React, { useEffect, useState } from "react";
import { fetchMe } from "../../services/authApi";

const ProfilePage = () => {
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetchMe().then(setUser).catch(console.error);
  }, []);

  if (!user) return <p style={{ color: "#94A3B8" }}>Loading...</p>;

  const roleColors = {
    ADMIN: { bg: "#EFF6FF", color: "#1D4ED8", border: "#BFDBFE" },
    IT: { bg: "#ECFDF5", color: "#065F46", border: "#6EE7B7" },
    USER: { bg: "#FFF7ED", color: "#92400E", border: "#FCD34D" },
  };
  const rc = roleColors[user.role] || roleColors.USER;

  return (
    <div>
      <div style={{ marginBottom: "28px" }}>
        <h1
          style={{
            fontSize: "22px",
            fontWeight: "800",
            color: "#0D1F35",
            letterSpacing: "-0.4px",
            margin: 0,
          }}
        >
          My Profile
        </h1>
        <p style={{ fontSize: "14px", color: "#64748B", marginTop: "4px" }}>
          Your account information
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "16px",
        }}
      >
        {/* User card */}
        <div
          style={{
            background: "#fff",
            border: "0.5px solid rgba(0,0,0,0.08)",
            borderRadius: "14px",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "16px 20px",
              borderBottom: "0.5px solid rgba(0,0,0,0.06)",
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "#EFF6FF",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#2563EB",
              }}
            >
              👤
            </div>
            <span
              style={{ fontSize: "14px", fontWeight: "700", color: "#0D1F35" }}
            >
              User information
            </span>
          </div>
          <div
            style={{
              padding: "16px 20px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            {[
              ["Full name", user.name],
              ["Email", user.email],
              [
                "Member since",
                new Date(user.created_at).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                }),
              ],
            ].map(([label, value]) => (
              <div
                key={label}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span
                  style={{
                    fontSize: "12px",
                    color: "#64748B",
                    fontWeight: "500",
                  }}
                >
                  {label}
                </span>
                <span
                  style={{
                    fontSize: "13px",
                    color: "#0D1F35",
                    fontWeight: "500",
                  }}
                >
                  {value}
                </span>
              </div>
            ))}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <span
                style={{
                  fontSize: "12px",
                  color: "#64748B",
                  fontWeight: "500",
                }}
              >
                Role
              </span>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: "700",
                  padding: "3px 10px",
                  borderRadius: "100px",
                  background: rc.bg,
                  color: rc.color,
                  border: `1px solid ${rc.border}`,
                }}
              >
                {user.role}
              </span>
            </div>
          </div>
        </div>

        {/* Org card */}
        <div
          style={{
            background: "#fff",
            border: "0.5px solid rgba(0,0,0,0.08)",
            borderRadius: "14px",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "16px 20px",
              borderBottom: "0.5px solid rgba(0,0,0,0.06)",
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "#EFF6FF",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              🏢
            </div>
            <span
              style={{ fontSize: "14px", fontWeight: "700", color: "#0D1F35" }}
            >
              Organization
            </span>
          </div>
          <div
            style={{
              padding: "16px 20px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            {[
              ["Name", user.org_name || "—"],
              ["Type", user.org_type || "—"],
              ["Org ID", (user.organization_id || "").slice(0, 8) + "..."],
            ].map(([label, value]) => (
              <div
                key={label}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span
                  style={{
                    fontSize: "12px",
                    color: "#64748B",
                    fontWeight: "500",
                  }}
                >
                  {label}
                </span>
                <span
                  style={{
                    fontSize: "13px",
                    color: "#0D1F35",
                    fontWeight: "500",
                    fontFamily: label === "Org ID" ? "monospace" : "inherit",
                  }}
                >
                  {value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
