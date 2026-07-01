const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function req(method, endpoint, body) {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

export const listProviders = () => req("GET", "/providers");
export const createProvider = (payload) => req("POST", "/providers", payload);
export const updateProvider = (id, payload) =>
  req("PUT", `/providers/${id}`, payload);
export const deleteProvider = (id) => req("DELETE", `/providers/${id}`);
export const getProviderModels = (id) => req("GET", `/providers/${id}/models`);
