import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// ── Auth pages ────────────────────────────────────────
import LoginPage from "./pages/auth/LoginPage";
import SignUpPage from "./pages/auth/SignUpPage";
import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import ActivatePage from "./pages/auth/ActivatePage";

// ── Layout ────────────────────────────────────────────
import DashboardLayout from "./components/layout/DashboardLayout";
import ProtectedRoute from "./components/ProtectedRoute";

// ── Admin pages ───────────────────────────────────────
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminRAGPage from "./pages/admin/AdminRAGPage";
import UsersPage from "./pages/admin/UsersPage";

// ── IT pages ─────────────────────────────────────────
import ITDashboard from "./pages/it/ITDashboard";
import RAGSpacesPage from "./pages/it/RAGSpacesPage";

// ── User pages ────────────────────────────────────────
import UserDashboard from "./pages/user/UserDashboard";
import UserAgentsPage from "./pages/user/UserAgentsPage";

// ── Shared pages ──────────────────────────────────────
import ProfilePage from "./pages/shared/ProfilePage";
import StartPage from "./pages/StartPage";

// ── Role redirect after login ─────────────────────────
import { getUser } from "./services/authApi";

const RoleRedirect = () => {
  const user = getUser();
  if (!user) return <Navigate to="/login" replace />;
  const redirects = { ADMIN: "/admin", IT: "/it", USER: "/user" };
  return <Navigate to={redirects[user.role] || "/login"} replace />;
};

// Placeholder for pages not yet built
const ComingSoon = ({ title }) => (
  <div style={{ padding: "48px 32px", textAlign: "center" }}>
    <div style={{ fontSize: 40, marginBottom: 12 }}>🚧</div>
    <h2
      style={{
        fontSize: 18,
        fontWeight: 600,
        color: "#1F2937",
        marginBottom: 6,
      }}
    >
      {title}
    </h2>
    <p style={{ fontSize: 13, color: "#6B7280" }}>
      This feature is coming in a future sprint.
    </p>
  </div>
);

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
            <Route path="/admin/users" element={<UsersPage />} />
            <Route path="/admin/rag" element={<AdminRAGPage />} />
            <Route
              path="/admin/providers"
              element={<ComingSoon title="Providers & API Keys" />}
            />
            <Route
              path="/admin/settings"
              element={<ComingSoon title="Org Settings" />}
            />
            <Route
              path="/admin/analytics"
              element={<ComingSoon title="Analytics" />}
            />
          </Route>
        </Route>

        {/* ══ Protected — IT only ══ */}
        <Route element={<ProtectedRoute roles={["IT"]} />}>
          <Route element={<DashboardLayout />}>
            <Route path="/it" element={<ITDashboard />} />
            <Route path="/it/rag" element={<RAGSpacesPage />} />
            <Route path="/it/agents" element={<ComingSoon title="Agents" />} />
            <Route
              path="/it/workflows"
              element={<ComingSoon title="Workflows" />}
            />
            <Route
              path="/it/console"
              element={<ComingSoon title="Test Console" />}
            />
            <Route
              path="/it/tuning"
              element={<ComingSoon title="Auto-Tuning" />}
            />
          </Route>
        </Route>

        {/* ══ Protected — EndUser only ══ */}
        <Route element={<ProtectedRoute roles={["USER"]} />}>
          <Route element={<DashboardLayout />}>
            <Route path="/user" element={<UserDashboard />} />
            <Route path="/user/agents" element={<UserAgentsPage />} />
            <Route
              path="/user/history"
              element={<ComingSoon title="Chat History" />}
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
