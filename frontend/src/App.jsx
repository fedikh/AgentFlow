import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// ── Auth pages ────────────────────────────────────────
import LoginPage from "./pages/auth/LoginPage";
import SignUpPage from "./pages/auth/SignUpPage";
import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";

// ── Layout ────────────────────────────────────────────
import DashboardLayout from "./components/layout/DashboardLayout";
import ProtectedRoute from "./components/ProtectedRoute";

// ── Admin pages ───────────────────────────────────────
import AdminDashboard from "./pages/admin/AdminDashboard";

// ── IT pages ─────────────────────────────────────────
import ITDashboard from "./pages/it/ITDashboard";
import RAGSpacesPage from "./pages/it/RAGSpacesPage";

// ── User pages ────────────────────────────────────────
import UserDashboard from "./pages/user/UserDashboard";

// ── Shared pages ──────────────────────────────────────
import ProfilePage from "./pages/shared/ProfilePage";
import UsersPage from "./pages/admin/UsersPage";
import ActivatePage from "./pages/auth/ActivatePage";
import StartPage from "./pages/StartPage";

// ── Role redirect after login ─────────────────────────
import { getUser } from "./services/authApi";

const RoleRedirect = () => {
  const user = getUser();
  if (!user) return <Navigate to="/login" replace />;
  const redirects = { ADMIN: "/admin", IT: "/it", USER: "/user" };
  return <Navigate to={redirects[user.role] || "/login"} replace />;
};

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── Public routes ── */}
        <Route path="/" element={<StartPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignUpPage />} />
        <Route path="/forgot" element={<ForgotPasswordPage />} />
        <Route path="/activate" element={<ActivatePage />} />

        {/* ── After login: redirect by role ── */}
        <Route path="/dashboard" element={<RoleRedirect />} />

        {/* ══ Protected — Admin only ══ */}
        <Route element={<ProtectedRoute roles={["ADMIN"]} />}>
          <Route element={<DashboardLayout />}>
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/rag" element={<RAGSpacesPage />} />
            <Route
              path="/admin/agents"
              element={
                <div style={{ padding: "32px" }}>Agents — coming soon</div>
              }
            />
            <Route
              path="/admin/workflows"
              element={
                <div style={{ padding: "32px" }}>Workflows — coming soon</div>
              }
            />
            <Route path="/admin/users" element={<UsersPage />} />
            <Route
              path="/admin/settings"
              element={
                <div style={{ padding: "32px" }}>
                  ORG settings — coming soon
                </div>
              }
            />
          </Route>
        </Route>

        {/* ══ Protected — IT only ══ */}
        <Route element={<ProtectedRoute roles={["IT"]} />}>
          <Route element={<DashboardLayout />}>
            <Route path="/it" element={<ITDashboard />} />
            <Route path="/it/rag" element={<RAGSpacesPage />} />
            <Route
              path="/it/agents"
              element={
                <div style={{ padding: "32px" }}>Agents — coming soon</div>
              }
            />
            <Route
              path="/it/workflows"
              element={
                <div style={{ padding: "32px" }}>Workflows — coming soon</div>
              }
            />
            <Route
              path="/it/connections"
              element={
                <div style={{ padding: "32px" }}>Connections — coming soon</div>
              }
            />
          </Route>
        </Route>

        {/* ══ Protected — EndUser only ══ */}
        <Route element={<ProtectedRoute roles={["USER"]} />}>
          <Route element={<DashboardLayout />}>
            <Route path="/user" element={<UserDashboard />} />
            <Route
              path="/user/chat"
              element={
                <div style={{ padding: "32px" }}>Chat — coming soon</div>
              }
            />
            <Route
              path="/user/history"
              element={
                <div style={{ padding: "32px" }}>History — coming soon</div>
              }
            />
          </Route>
        </Route>

        {/* ══ Protected — All roles ══ */}
        <Route element={<ProtectedRoute />}>
          <Route element={<DashboardLayout />}>
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
        </Route>

        {/* 404 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
