const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request(method, endpoint, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE_URL}${endpoint}`, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

// Users
export const inviteUser = (email, role, departmentIds) =>
  request("POST", "/users/invite", {
    email,
    role,
    department_ids: departmentIds,
  });
export const activateUser = (token, name, password) =>
  request("POST", "/users/activate", { token, name, password });
export const listUsers = () => request("GET", "/users/");
export const updateUser = (userId, data) =>
  request("PUT", `/users/${userId}`, data);
// Preview a user's owned RAG spaces + eligible transfer targets before deletion
export const getUserTransferInfo = (userId) =>
  request("GET", `/users/${userId}/transfer-info`);
// deleteUser optionally carries a { transfers: {deptKey: targetItId} } map.
// Always send a JSON object ({} when no transfers) so the DELETE body parses.
export const deleteUser = (userId, body = {}) =>
  request("DELETE", `/users/${userId}`, body);
export const resendInvite = (userId) =>
  request("POST", `/users/${userId}/resend`);

// Departments
export const createDepartment = (name) =>
  request("POST", "/users/departments", { name });
export const listDepartments = () => request("GET", "/users/departments");
export const deleteDepartment = (deptId) =>
  request("DELETE", `/users/departments/${deptId}`);
