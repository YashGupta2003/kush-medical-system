import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Users as UsersIcon, UserPlus, ShieldOff } from "lucide-react";
import { api } from "../api/client.js";

export default function Users() {
  const [users, setUsers] = useState([]);
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("staff");
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  function refresh() {
    api.listUsers().then(setUsers);
  }
  useEffect(() => { refresh(); }, []);

  async function handleCreate(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.createUser({ username, full_name: fullName || null, password, role });
      setUsername(""); setFullName(""); setPassword(""); setRole("staff");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate(id) {
    await api.deactivateUser(id);
    refresh();
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="page-content"
    >
      <div className="card">
        <h2 style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <UsersIcon size={24} color="var(--primary-500)" /> Manage Staff Accounts
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 0 }}>
          Staff can upload/review bills, record sales, and view stock — but can't see cost prices,
          Analytics, or GST reports. Only the Owner has full access.
        </p>
        <form onSubmit={handleCreate} style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end", marginTop: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 500 }}>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} required style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 500 }}>Full name</label>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 500 }}>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 500 }}>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)} style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }}>
              <option value="staff">Staff</option>
              <option value="owner">Owner</option>
            </select>
          </div>
          <button type="submit" disabled={saving} className="btn btn-primary" style={{ padding: "8px 16px", display: "flex", alignItems: "center", gap: 6 }}>
            <UserPlus size={16} />
            {saving ? "Adding..." : "Add account"}
          </button>
        </form>
        {error && <p style={{ color: "var(--danger)", marginTop: 12 }}>{error}</p>}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, color: "var(--text-main)" }}>All accounts</h3>
        <table className="table">
          <thead><tr><th>Username</th><th>Full name</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.full_name || "—"}</td>
                <td><span className={`badge ${u.role === "owner" ? "auto" : "manual"}`}>{u.role}</span></td>
                <td>{u.is_active ? <span className="badge auto">active</span> : <span className="badge unmatched">disabled</span>}</td>
                <td>
                  {u.is_active && (
                    <button className="btn btn-secondary" onClick={() => handleDeactivate(u.id)} style={{ padding: "4px 8px", fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}>
                      <ShieldOff size={14} /> Deactivate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}