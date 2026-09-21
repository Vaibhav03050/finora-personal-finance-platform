/* Thin fetch wrapper around the FastAPI backend. */
const API_BASE = "/api/v1";

const Api = {
  token() { return localStorage.getItem("finora_token"); },
  setToken(t) { localStorage.setItem("finora_token", t); },
  clearToken() { localStorage.removeItem("finora_token"); },

  async request(path, { method = "GET", body, isForm = false } = {}) {
    const headers = {};
    if (!isForm) headers["Content-Type"] = "application/json";
    const token = this.token();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const resp = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
    });

    let json;
    try { json = await resp.json(); }
    catch { json = { success: false, error: { message: "Unexpected server response." } }; }

    if (!resp.ok || json.success === false) {
      const msg = (json.error && json.error.message) || json.detail || "Something went wrong.";
      const err = new Error(msg);
      err.status = resp.status;
      throw err;
    }
    return json; // { success, data, meta }
  },

  get(path) { return this.request(path); },
  post(path, body) { return this.request(path, { method: "POST", body }); },
  put(path, body) { return this.request(path, { method: "PUT", body }); },
  del(path) { return this.request(path, { method: "DELETE" }); },
  upload(path, file, fieldName = "file", fields = {}) {
    const form = new FormData();
    form.append(fieldName, file);
    Object.entries(fields || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") form.append(key, value);
    });
    return this.request(path, { method: "POST", body: form, isForm: true });
  },
};
