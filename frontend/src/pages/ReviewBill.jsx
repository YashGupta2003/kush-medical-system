import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client.js";

const FIELDS = [
  "raw_name", "qty", "free_qty", "mrp", "rate",
  "discount_pct", "special_discount_pct", "gst_pct",
];

export default function ReviewBill() {
  const { billId } = useParams();
  const [bill, setBill] = useState(null);
  const [rows, setRows] = useState({});          // id -> edited field values
  const [applyFlags, setApplyFlags] = useState({}); // id -> apply_to_master_list bool
  const [changeSummary, setChangeSummary] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getBill(billId).then((b) => {
      setBill(b);
      const initialRows = {};
      const initialFlags = {};
      b.items.forEach((item) => {
        initialRows[item.id] = { ...item };
        initialFlags[item.id] = item.match_status !== "unmatched";
      });
      setRows(initialRows);
      setApplyFlags(initialFlags);
    });
  }, [billId]);

  function updateField(itemId, field, value) {
    setRows((prev) => ({
      ...prev,
      [itemId]: { ...prev[itemId], [field]: value },
    }));
  }

  async function handleConfirm() {
    setSaving(true);
    setError(null);
    try {
      const items = Object.values(rows).map((r) => ({
        id: r.id,
        raw_name: r.raw_name,
        qty: Number(r.qty) || 0,
        free_qty: Number(r.free_qty) || 0,
        mrp: Number(r.mrp) || 0,
        rate: Number(r.rate) || 0,
        discount_pct: Number(r.discount_pct) || 0,
        special_discount_pct: Number(r.special_discount_pct) || 0,
        gst_pct: Number(r.gst_pct) || 0,
        medicine_id: r.medicine_id || null,
        apply_to_master_list: !!applyFlags[r.id],
      }));
      const summary = await api.confirmBill({ bill_id: Number(billId), items });
      setChangeSummary(summary);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (!bill) return <p>Loading...</p>;

  if (changeSummary) {
    return (
      <div className="card">
        <h2>Confirmed — here's exactly what changed</h2>
        {changeSummary.length === 0 && <p>No master rate list changes were made.</p>}
        <table>
          <thead>
            <tr><th>Medicine</th><th>Column</th><th>Old value</th><th>New value</th></tr>
          </thead>
          <tbody>
            {changeSummary.map((c, i) => (
              <tr key={i}>
                <td>{c.medicine_name}</td>
                <td>{c.field === "net_rate" ? "Cost price (NET RATE)" : "MRP"}</td>
                <td>{c.old_value ?? "—"}</td>
                <td><strong>{c.new_value ?? "—"}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div>
      <div className="card">
        <div className="flex-between">
          <div>
            <h2>Review bill #{bill.id}</h2>
            <p style={{ color: "#666", fontSize: 13 }}>
              {bill.distributor_name || "Unknown distributor"} · {bill.invoice_no || "no invoice no."} ·
              {" "}{bill.year}-{String(bill.month).padStart(2, "0")}
            </p>
          </div>
          <button onClick={handleConfirm} disabled={saving}>
            {saving ? "Saving..." : "Confirm all & update rate list"}
          </button>
        </div>
        {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      </div>

      <div className="card" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Name (edit if wrong)</th>
              <th>Matched to</th>
              <th>Qty</th>
              <th>Free</th>
              <th>MRP</th>
              <th>Rate</th>
              <th>Disc%</th>
              <th>Sp.Disc%</th>
              <th>GST%</th>
              <th>Cost/unit</th>
              <th>Update list?</th>
            </tr>
          </thead>
          <tbody>
            {Object.values(rows).map((r) => (
              <tr key={r.id}>
                <td>
                  <input
                    style={{ width: 140 }}
                    value={r.raw_name || ""}
                    onChange={(e) => updateField(r.id, "raw_name", e.target.value)}
                  />
                </td>
                <td>
                  {r.suggested_medicine_name ? (
                    <span className={`badge ${r.match_status}`}>
                      {r.suggested_medicine_name} ({Math.round(r.match_confidence || 0)}%)
                    </span>
                  ) : (
                    <span className="badge unmatched">no match — pick manually</span>
                  )}
                </td>
                {["qty", "free_qty", "mrp", "rate", "discount_pct", "special_discount_pct", "gst_pct"].map((f) => (
                  <td key={f}>
                    <input
                      type="number"
                      style={{ width: 60 }}
                      value={r[f] ?? ""}
                      onChange={(e) => updateField(r.id, f, e.target.value)}
                    />
                  </td>
                ))}
                <td>{r.computed_cost_per_unit}</td>
                <td>
                  <input
                    type="checkbox"
                    checked={!!applyFlags[r.id]}
                    onChange={(e) =>
                      setApplyFlags((prev) => ({ ...prev, [r.id]: e.target.checked }))
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
