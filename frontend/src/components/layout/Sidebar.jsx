import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { getUser, clearSession, logout } from "../../services/authApi";
import "../../styles/layoutStyles/Sidebar.css";

const Icon = ({ d, d2 }) => (
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
  </svg>
);

const NAV = {
  ADMIN: [
    {
      section: "CORE",
      items: [
        {
          to: "/admin",
          label: "Dashboard",
          icon: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
        },
        {
          to: "/admin/rag",
          label: "RAG Spaces",
          icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z",
          icon2: "M14 2v6h6",
        },
        {
          to: "/admin/agents",
          label: "Agents",
          icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
        },
        {
          to: "/admin/workflows",
          label: "Workflows",
          icon: "M22 12h-4l-3 9L9 3l-3 9H2",
        },
      ],
    },
    {
      section: "MANAGEMENT",
      businessOnly: true,
      items: [
        {
          to: "/admin/users",
          label: "Users",
          icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2",
          icon2: "M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
        },
        {
          to: "/admin/settings",
          label: "Org Settings",
          icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z",
        },
      ],
    },
    {
      section: "SETTINGS",
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
  IT: [
    {
      section: "CORE",
      items: [
        {
          to: "/it",
          label: "Dashboard",
          icon: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
        },
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
      section: "SETTINGS",
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
  USER: [
    {
      section: "CORE",
      items: [
        {
          to: "/user",
          label: "Dashboard",
          icon: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
        },
        {
          to: "/user/agents",
          label: "Agents",
          icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
        },
      ],
    },
    {
      section: "SETTINGS",
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
                <Icon d={item.icon} d2={item.icon2} />
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
          <div className="sidebar-user-name">{user?.name || "User"}</div>
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
