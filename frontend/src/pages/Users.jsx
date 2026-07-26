import { useEffect, useState } from "react";
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
    <div>
      <div className="card">
        <h2>👥 Manage Staff Accounts</h2>
        <p style={{ color: "#666", fontSize: 13 }}>
          Staff can upload/review bills, record sales, and view stock — but can't see cost prices,
          Analytics, or GST reports. Only the Owner has full access.
        </p>
        <form onSubmit={handleCreate} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div>
            <label style={{ fontSize: 12, color: "#666" }}>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "#666" }}>Full name</label>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "#666" }}>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "#666" }}>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="staff">Staff</option>
              <option value="owner">Owner</option>
            </select>
          </div>
          <button type="submit" disabled={saving}>{saving ? "Adding..." : "Add account"}</button>
        </form>
        {error && <p style={{ color: "#b91c1c", marginTop: 10 }}>{error}</p>}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>All accounts</h3>
        <table>
          <thead><tr><th>Username</th><th>Full name</th><th>Role</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.full_name || "—"}</td>
                <td><span className={`badge ${u.role === "owner" ? "auto" : "manual"}`}>{u.role}</span></td>
                <td>{u.is_active ? <span className="badge auto">active</span> : <span className="badge unmatched">disabled</span>}</td>
                <td>{u.is_active && <button className="secondary" onClick={() => handleDeactivate(u.id)}>Deactivate</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}