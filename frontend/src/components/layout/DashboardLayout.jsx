import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import "../../styles/layoutStyles/DashboardLayout.css";


const DashboardLayout = () => (
  <div className="layout-root">
    <Sidebar />
    <main className="layout-main">
      <Outlet />
    </main>
  </div>
);

export default DashboardLayout;