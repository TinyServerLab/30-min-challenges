const TOKENS_KEY = "finance_tokens";

function getTokens() {
  const raw = localStorage.getItem(TOKENS_KEY);
  return raw ? JSON.parse(raw) : null;
}

function setTokens(tokens) {
  localStorage.setItem(TOKENS_KEY, JSON.stringify(tokens));
}

function clearTokens() {
  localStorage.removeItem(TOKENS_KEY);
}

async function refreshTokens() {
  const tokens = getTokens();
  if (!tokens?.refresh_token) throw new Error("no refresh token");
  const res = await fetch("/api/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });
  if (!res.ok) {
    clearTokens();
    throw new Error("refresh failed");
  }
  const data = await res.json();
  setTokens(data);
  return data;
}

async function request(path, { method = "GET", body, isForm = false, raw = false } = {}) {
  let tokens = getTokens();

  const doFetch = async () => {
    const headers = {};
    if (!isForm) headers["Content-Type"] = "application/json";
    if (tokens?.access_token) headers["Authorization"] = `Bearer ${tokens.access_token}`;
    return fetch(`/api${path}`, {
      method,
      headers,
      body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
    });
  };

  let res = await doFetch();

  if (res.status === 401 && tokens?.refresh_token) {
    try {
      tokens = await refreshTokens();
      res = await doFetch();
    } catch {
      clearTokens();
      window.location.href = "/login";
      throw new Error("Session expired");
    }
  }

  if (!res.ok) {
    let detail = "Request failed";
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }

  if (raw) return res;
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  del: (path) => request(path, { method: "DELETE" }),
  raw: (path) => request(path, { raw: true }),
};

export const authApi = {
  async login(email, password) {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    setTokens(data);
    return data;
  },
  logout() {
    clearTokens();
  },
  isLoggedIn() {
    return !!getTokens()?.access_token;
  },
};
