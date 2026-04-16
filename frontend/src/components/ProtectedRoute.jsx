import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { isLoggedIn, getUser } from "../services/authApi";

/**
 * ProtectedRoute — guards routes by:
 * 1. Checking the user is logged in (JWT in localStorage)
 * 2. Optionally checking the user has one of the allowed roles
 *
 * Usage in App.jsx:
 *   <Route element={<ProtectedRoute />}>                     // any logged-in user
 *   <Route element={<ProtectedRoute roles={["ADMIN"]} />}>   // ADMIN only
 */
const ProtectedRoute = ({ roles }) => {
  const loggedIn = isLoggedIn();
  const user = getUser();

  // Not logged in → redirect to login
  if (!loggedIn || !user) {
    return <Navigate to="/login" replace />;
  }

  // Role check — if roles specified and user's role not in list → redirect
  if (roles && !roles.includes(user.role)) {
    // Redirect each role to their own dashboard
    const redirects = { ADMIN: "/admin", IT: "/it", USER: "/user" };
    return <Navigate to={redirects[user.role] || "/login"} replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
