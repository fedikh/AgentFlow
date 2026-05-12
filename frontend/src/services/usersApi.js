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
export const deleteUser = (userId) => request("DELETE", `/users/${userId}`);
export const resendInvite = (userId) =>
  request("POST", `/users/${userId}/resend`);

// Departments
export const createDepartment = (name) =>
  request("POST", "/users/departments", { name });
export const listDepartments = () => request("GET", "/users/departments");
export const deleteDepartment = (deptId) =>
  request("DELETE", `/users/departments/${deptId}`);
