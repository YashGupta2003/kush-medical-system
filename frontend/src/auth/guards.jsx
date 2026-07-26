import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";

export function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <p style={{ padding: 20 }}>Loading...</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return children;
}

export function RequireOwner({ children }) {
  const { user, loading, isOwner } = useAuth();
  const location = useLocation();

  if (loading) return <p style={{ padding: 20 }}>Loading...</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (!isOwner) {
    return (
      <div className="card">
        <h2>🔒 Owner access only</h2>
        <p style={{ color: "#666" }}>This section (financial data / reports) is restricted to the shop Owner.</p>
      </div>
    );
  }
  return children;
}
