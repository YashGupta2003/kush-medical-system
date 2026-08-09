import { createContext, useContext, useEffect, useState } from "react";
import {
  api, getToken, setToken, clearToken, setUnauthorizedHandler,
  getRefreshToken, setRefreshToken,
} from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);   // { username, role, full_name }
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // When the global 401 handler fires (after silent refresh also failed),
    // clear user state to show the login page.
    setUnauthorizedHandler(() => setUser(null));

    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api.me()
      .then((u) => setUser(u))
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  async function login(username, password) {
    const res = await api.login(username, password);
    setToken(res.access_token);
    // Priority 2a: store the refresh token for silent refresh on 401
    if (res.refresh_token) setRefreshToken(res.refresh_token);
    setUser({ username: res.username, role: res.role, full_name: res.full_name });
  }

  async function logout() {
    // Best-effort server-side token revocation
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      api.logout(refreshToken).catch(() => {});
    }
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isOwner: user?.role === "owner" }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}