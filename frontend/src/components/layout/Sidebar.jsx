import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { getUser, clearSession, logout } from "../../services/authApi";
import "../../styles/layoutStyles/Sidebar.css";

const Icon = ({ d, d2, d3 }) => (
  <svg
    width="15"
    height="15"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d={d} />
    {d2 && <path d={d2} />}
    {d3 && <path d={d3} />}
  </svg>
);

// ══════════════════════════════════════════════════════
// NAVIGATION BY ROLE
// ══════════════════════════════════════════════════════
const NAV = {
  // ── ADMIN ──────────────────────────────────────────
  ADMIN: [
    {
      section: "OVERVIEW",
      items: [
        {
          to: "/admin",
          label: "Dashboard",
          icon: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
        },
      ],
    },
    {
      section: "MANAGEMENT",
      businessOnly: true,
      items: [
        {
          to: "/admin/users",
          label: "Users & Departments",
          icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2",
          icon2: "M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
        },
        {
          to: "/admin/rag",
          label: "RAG Spaces",
          icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z",
          icon2: "M14 2v6h6",
        },
      ],
    },
    {
      section: "CONFIGURATION",
      businessOnly: true,
      items: [
        {
          to: "/admin/providers",
          label: "Providers & API Keys",
          icon: "M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4",
        },
        {
          to: "/admin/settings",
          label: "Org Settings",
          icon: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z",
          icon2: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
        },
      ],
    },
    {
      section: "MONITORING",
      businessOnly: true,
      items: [
        {
          to: "/admin/analytics",
          label: "Analytics",
          icon: "M18 20V10M12 20V4M6 20v-6",
        },
      ],
    },
    {
      section: "ACCOUNT",
      items: [
        {
          to: "/profile",
          label: "Profile",
          icon: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2",
          icon2: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
        },
      ],
    },
  ],

  // ── IT ─────────────────────────────────────────────
  IT: [
    {
      section: "OVERVIEW",
      items: [
        {
          to: "/it",
          label: "Dashboard",
          icon: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
        },
      ],
    },
    {
      section: "BUILD",
      items: [
        {
          to: "/it/rag",
          label: "RAG Spaces",
          icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z",
          icon2: "M14 2v6h6",
        },
        {
          to: "/it/agents",
          label: "Agents",
          icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
        },
        {
          to: "/it/workflows",
          label: "Workflows",
          icon: "M22 12h-4l-3 9L9 3l-3 9H2",
        },
      ],
    },
    {
      section: "TOOLS",
      items: [
        {
          to: "/it/console",
          label: "Test Console",
          icon: "M4 17l6-6-6-6M12 19h8",
        },
        {
          to: "/it/tuning",
          label: "Auto-Tuning",
          icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z",
        },
      ],
    },
    {
      section: "ACCOUNT",
      items: [
        {
          to: "/profile",
          label: "Profile",
          icon: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2",
          icon2: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
        },
      ],
    },
  ],

  // ── END USER ───────────────────────────────────────
  USER: [
    {
      section: "OVERVIEW",
      items: [
        {
          to: "/user",
          label: "Dashboard",
          icon: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
        },
      ],
    },
    {
      section: "AI ASSISTANTS",
      items: [
        {
          to: "/user/agents",
          label: "My Agents",
          icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
        },
        {
          to: "/user/history",
          label: "Chat History",
          icon: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
        },
      ],
    },
    {
      section: "ACCOUNT",
      items: [
        {
          to: "/profile",
          label: "Profile",
          icon: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2",
          icon2: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
        },
      ],
    },
  ],
};

// ══════════════════════════════════════════════════════
// SIDEBAR COMPONENT
// ══════════════════════════════════════════════════════
const Sidebar = () => {
  const user = getUser();
  const role = user?.role || "USER";
  const orgType = user?.org_type || "PERSONAL";
  const allSections = NAV[role] || NAV.USER;
  const sections = allSections.filter(
    (sec) => !sec.businessOnly || orgType === "BUSINESS",
  );

  const navigate = useNavigate();
  const [showConfirm, setShowConfirm] = React.useState(false);

  const handleLogout = () => {
    logout().finally(() => {
      clearSession();
      navigate("/login");
    });
  };

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "??";

  // Role badge colors
  const roleBadge = {
    ADMIN: { bg: "#FEF2F2", color: "#991B1B", label: "Admin" },
    IT: { bg: "#EFF6FF", color: "#1E40AF", label: "IT" },
    USER: { bg: "#F0FDF4", color: "#166534", label: "User" },
  };
  const rb = roleBadge[role] || roleBadge.USER;

  return (
    <aside className="sidebar">
      {/* ── Brand ── */}
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">
          <img
            src="/src/assets/Logo/Agentflowlogowithouttext.png"
            alt="AgentFlow"
            onError={(e) => {
              e.target.style.display = "none";
              e.target.parentElement.style.background =
                "linear-gradient(135deg,#2563EB,#6366f1)";
            }}
          />
        </div>
        <div>
          <div className="sidebar-brand-name">
            AgentFlow<span>.AI</span>
          </div>
          <div className="sidebar-brand-version">v1.0</div>
        </div>
      </div>

      {/* ── Nav sections ── */}
      <nav className="sidebar-nav">
        {sections.map((sec, si) => (
          <div key={si}>
            <div className="sidebar-section-label">{sec.section}</div>
            {sec.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={
                  item.to === "/admin" ||
                  item.to === "/it" ||
                  item.to === "/user"
                }
                className={({ isActive }) =>
                  `sidebar-link ${isActive ? "active" : ""}`
                }
              >
                <Icon d={item.icon} d2={item.icon2} d3={item.d3} />
                <span>{item.label}</span>
              </NavLink>
            ))}
            {si < sections.length - 1 && <div className="sidebar-divider" />}
          </div>
        ))}
      </nav>

      {/* ── User bottom ── */}
      <div className="sidebar-user">
        <div className="sidebar-user-avatar">{initials}</div>
        <div style={{ overflow: "hidden", flex: 1 }}>
          <div className="sidebar-user-name">
            {user?.name || "User"}
            <span
              style={{
                fontSize: 9,
                fontWeight: 600,
                marginLeft: 6,
                padding: "1px 5px",
                borderRadius: 4,
                background: rb.bg,
                color: rb.color,
                verticalAlign: "middle",
              }}
            >
              {rb.label}
            </span>
          </div>
          <div className="sidebar-user-email">{user?.email || ""}</div>
        </div>
        <button
          className="sidebar-logout-btn"
          onClick={() => setShowConfirm(true)}
          title="Logout"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>

      {/* ── Logout confirm modal ── */}
      {showConfirm && (
        <div className="logout-overlay" onClick={() => setShowConfirm(false)}>
          <div className="logout-modal" onClick={(e) => e.stopPropagation()}>
            <div className="logout-modal-icon">
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </div>
            <div className="logout-modal-title">Sign out?</div>
            <div className="logout-modal-sub">
              Are you sure you want to sign out of AgentFlow?
            </div>
            <div className="logout-modal-actions">
              <button
                className="logout-btn-cancel"
                onClick={() => setShowConfirm(false)}
              >
                Cancel
              </button>
              <button className="logout-btn-confirm" onClick={handleLogout}>
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
