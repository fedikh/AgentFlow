import React, { useEffect } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import Sidebar from "./Sidebar";
import { checkSession } from "../../services/authApi";
import "../../styles/layoutStyles/DashboardLayout.css";

const DashboardLayout = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // Check if user still exists in DB (handles deleted users)
    checkSession().then((valid) => {
      if (!valid) {
        navigate("/login");
      }
    });
  }, [navigate]);

  return (
    <div className="layout-root">
      <Sidebar />
      <main className="layout-main">
        <Outlet />
      </main>
    </div>
  );
};

export default DashboardLayout;
