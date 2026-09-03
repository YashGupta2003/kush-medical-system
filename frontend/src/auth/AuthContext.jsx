import { createContext, useContext, useEffect, useState } from "react";
import {
  api, getToken, setToken, clearToken, setUnauthorizedHandler,
  getRefreshToken, setRefreshToken,
} from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);   // { username, role, full_name, tenant_id, shop_name }
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
      .catch((e) => {
        console.error("Auth check failed:", e);
        clearToken();
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(username, password, tenant_id) {
    const res = await api.login(username, password, tenant_id);
    setToken(res.access_token);
    // Priority 2a: store the refresh token for silent refresh on 401
    if (res.refresh_token) setRefreshToken(res.refresh_token);
    setUser({
      username: res.username,
      role: res.role,
      full_name: res.full_name,
      tenant_id: res.tenant_id,
      shop_name: res.shop_name,
    });
  }

  /**
   * loginWithTokens — used by the registration flow where tokens come
   * directly from the POST /register response, not from a login call.
   * Skips the API call; uses the tokens + user data from the register response.
   */
  async function loginWithTokens(accessToken, refreshToken, userData) {
    setToken(accessToken);
    if (refreshToken) setRefreshToken(refreshToken);
    setUser({
      username: userData.username,
      role: userData.role,
      full_name: userData.full_name,
      tenant_id: userData.tenant_id,
      shop_name: userData.shop_name,
    });
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
    <AuthContext.Provider value={{ user, loading, login, loginWithTokens, logout, isOwner: user?.role === "owner" }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}