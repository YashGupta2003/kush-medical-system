import { createContext, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api, getToken, setToken, clearToken, setUnauthorizedHandler,
  getRefreshToken, setRefreshToken,
} from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      // Optional: if they get a 401, send them to login
      navigate("/login");
    });

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
  }, [navigate]);

  async function login(username, password, tenant_id) {
    const res = await api.login(username, password, tenant_id);
    setToken(res.access_token);
    if (res.refresh_token) setRefreshToken(res.refresh_token);
    setUser({
      username: res.username,
      role: res.role,
      full_name: res.full_name,
      tenant_id: res.tenant_id,
      shop_name: res.shop_name,
    });
  }

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
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      api.logout(refreshToken).catch(() => {});
    }
    clearToken();
    setUser(null);
    navigate("/");
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