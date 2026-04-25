const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

// ── Helpers ───────────────────────────────────────────
async function post(endpoint, body) {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body !== null ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

async function get(endpoint) {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "include", // send cookies automatically
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

// ── Session helpers ───────────────────────────────────
// Only store non-sensitive user info in localStorage
// The JWT stays in the httpOnly cookie — never accessible to JS
export const saveSession = (data) => {
  localStorage.setItem("user", JSON.stringify(data.user));
};

export const getUser = () => {
  const u = localStorage.getItem("user");
  return u ? JSON.parse(u) : null;
};

export const clearSession = () => {
  localStorage.removeItem("user");
};

export const isLoggedIn = () => !!getUser();

// ── Auth API calls ────────────────────────────────────
export const login = (email, password) =>
  post("/auth/login", { email, password });
export const register = (payload) => post("/auth/register", payload);
export const logout = () => post("/auth/logout", null);
export const forgotPassword = (email) =>
  post("/auth/forgot-password", { email });
export const verifyOtp = (email, otp) =>
  post("/auth/verify-otp", { email, otp });
export const resetPassword = (email, otp, new_password) =>
  post("/auth/reset-password", { email, otp, new_password });
export const fetchMe = () => get("/auth/me");

export const checkSession = async () => {
  try {
    await get("/auth/me");
    return true;
  } catch (err) {
    clearSession();
    return false;
  }
};
