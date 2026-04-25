import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { isLoggedIn, getUser } from "../services/authApi";

/**
 * PublicRoute — guards auth pages (login, signup, forgot).
 *
 * If the user is already logged in:
 *   - ADMIN → clear session, show login (Admin always re-authenticates)
 *   - IT/USER → redirect to their dashboard (don't show login)
 *
 * If not logged in → show the page normally.
 */
const PublicRoute = () => {
  if (!isLoggedIn()) {
    return <Outlet />; // not logged in → show login/signup/forgot
  }

  const user = getUser();

  if (!user) {
    return <Outlet />; // corrupted session → show login
  }

  // Admin always sees login (LoginPage handles clearSession itself)
  if (user.role === "ADMIN") {
    return <Outlet />;
  }

  // IT/USER → redirect to their dashboard
  const redirects = { IT: "/it", USER: "/user" };
  return <Navigate to={redirects[user.role] || "/login"} replace />;
};

export default PublicRoute;
