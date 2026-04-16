import React from "react";
import { useNavigate } from "react-router-dom";
import { clearSession, getUser } from "../../services/authApi";
import "../../styles/layoutStyles/Navbar.css";

const Navbar = () => {
  const navigate = useNavigate();
  const user = getUser();

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "??";

  const handleLogout = () => {
    clearSession();
    navigate("/login");
  };

  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="navbar-icon">
          <img
            src="/src/assets/Logo/Agentflowlogowithouttext.png"
            alt="AgentFlow"
            onError={(e) => {
              e.target.style.display = "none";
            }}
          />
        </div>
        <div>
          <div className="navbar-title">
            AgentFlow<span className="navbar-dot">.AI</span>
          </div>
          <div className="navbar-sub">AGENTS STUDIO · v1.0</div>
        </div>
      </div>

      <div className="navbar-right">
        <div className="navbar-user">
          <div className="navbar-avatar">{initials}</div>
          <div className="navbar-info">
            <div className="navbar-name">{user?.name || "User"}</div>
            <div className="navbar-role">{user?.role || "—"}</div>
          </div>
        </div>
        <button className="navbar-logout" onClick={handleLogout}>
          Logout
        </button>
      </div>
    </header>
  );
};

export default Navbar;
