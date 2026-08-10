

import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../api/client.js";

function formatMoney(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function getScoreColor(score) {
  if (score >= 70) return "#16a34a"; // green
  if (score >= 40) return "#ca8a04"; // amber
  return "#dc2626"; // red
}

function getConfidenceBadge(conf) {
  if (conf === "high") return "auto"; // green
  if (conf === "medium") return "manual"; // yellow
  if (conf === "low") return "unmatched"; // red
  return "manual";
}

// ---------------------------------------------------------------------------
// Expanded Detail View
// ---------------------------------------------------------------------------
function DistributorDetail({ id }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getTrustScore(id)
      .then(setDetail)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div style={{ padding: 12, color: "#888", fontSize: 13 }}>Loading details...</div>;
  if (!detail) return <div style={{ padding: 12, color: "#888", fontSize: 13 }}>Failed to load details.</div>;

  return (
    <div className="trust-detail-pane">
      <h4>Contributing Factors</h4>
      <ul style={{ margin: "4px 0 16px", paddingLeft: 20, fontSize: 13, color: "#444" }}>
        {detail.contributing_factors?.map((f, i) => <li key={i}>{f}</li>) || <li>No specific factors listed.</li>}
      </ul>

      {detail.batch_collisions?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h4>Batch Collisions</h4>
          {detail.batch_collisions.map((c, i) => (
            <div key={i} style={{ fontSize: 13, color: "#555", marginBottom: 4 }}>
              <strong>{c.medicine_name}</strong> (Batch: {c.normalized_batch_number}) shared with {c.other_distributor_names?.join(", ")}
            </div>
          ))}
        </div>
      )}

      {detail.rate_outlier_summary && detail.rate_outlier_summary.length > 0 && (
        <div>
          <h4>Rate Comparison (vs Market Average)</h4>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={detail.rate_outlier_summary} layout="vertical" margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" fontSize={11} tickFormatter={(val) => "₹" + val} />
              <YAxis dataKey="medicine_name" type="category" fontSize={11} width={150} />
              <Tooltip formatter={(val) => "₹" + val} />
              <Bar dataKey="avg_rate" fill="#8884d8" name="This Distributor" />
              <Bar dataKey="market_avg_rate" fill="#82ca9d" name="Market Avg" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 1: Trust Scores
// ---------------------------------------------------------------------------
function TrustScoresTab() {
  const [distributors, setDistributors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    api.getTrustScores()
      .then((data) => {
        // Sort ascending by default (most concerning first)
        const sorted = (data || []).sort((a, b) => (a.score || 0) - (b.score || 0));
        setDistributors(sorted);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ color: "#888", fontSize: 13 }}>Loading trust scores...</p>;

  return (
    <div className="card">
      <table className="trust-table">
        <thead>
          <tr>
            <th>Distributor Name</th>
            <th>Score</th>
            <th>Confidence</th>
            <th>Factors Count</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {distributors.map((d) => (
            <React.Fragment key={d.distributor_id}>
              <tr>
                <td style={{ fontWeight: 600 }}>{d.distributor_name}</td>
                <td>
                  <span style={{ color: getScoreColor(d.score), fontWeight: "bold", fontSize: 16 }}>
                    {d.score}
                  </span>
                  <span style={{ fontSize: 12, color: "#888" }}>/100</span>
                </td>
                <td>
                  <span className={`badge ${getConfidenceBadge(d.confidence)}`}>{d.confidence}</span>
                </td>
                <td style={{ color: "#666" }}>{d.contributing_factors?.length || 0}</td>
                <td>
                  <button className="secondary" style={{ fontSize: 12, padding: "4px 8px" }} onClick={() => setExpandedId(expandedId === d.distributor_id ? null : d.distributor_id)}>
                    {expandedId === d.distributor_id ? "Hide Details" : "View Details"}
                  </button>
                </td>
              </tr>
              {expandedId === d.distributor_id && (
                <tr>
                  <td colSpan={5} style={{ padding: 0, borderBottom: "1px solid #eee" }}>
                    <DistributorDetail id={d.distributor_id} />
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
          {distributors.length === 0 && (
            <tr>
              <td colSpan={5} style={{ textAlign: "center", color: "#888", padding: 20 }}>No distributors found.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 2: Batch Collisions
// ---------------------------------------------------------------------------
function BatchCollisionsTab() {
  const [collisions, setCollisions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getBatchCollisions(365)
      .then((data) => setCollisions(data || []))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ color: "#888", fontSize: 13 }}>Loading batch collisions...</p>;

  if (collisions.length === 0) return <p style={{ color: "#888", fontSize: 13 }}>No batch collisions found in the last 365 days.</p>;

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {collisions.map((c, i) => (
        <div key={i} className="card" style={{ marginBottom: 0 }}>
          <div className="flex-between">
            <h4 style={{ margin: 0 }}>{c.medicine_name}</h4>
            <span className="badge unmatched">Collision Detected</span>
          </div>
          <div style={{ marginTop: 8, fontSize: 13, color: "#555" }}>
            <div><strong>Normalized Batch:</strong> {c.normalized_batch_number}</div>
            <div><strong>Distributors Involved:</strong> {c.distributor_names?.join(" & ") || "Unknown"}</div>
            <div><strong>Occurrences:</strong> {c.occurrence_count} times</div>
            {c.date_range && <div><strong>Date Range:</strong> {c.date_range.start} to {c.date_range.end}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function TrustScore() {
  const [tab, setTab] = useState("scores");

  return (
    <div>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>🛡️ Supply Chain Trust Score</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          Composite trust scoring based on historical purchasing patterns, rate consistency, and batch collisions. 
          Use this to evaluate the reliability and integrity of your supply chain partners.
        </p>
        <div className="tabs" style={{ marginBottom: 0 }}>
          <button className={`tab-button ${tab === "scores" ? "active" : ""}`} onClick={() => setTab("scores")}>Trust Scores</button>
          <button className={`tab-button ${tab === "collisions" ? "active" : ""}`} onClick={() => setTab("collisions")}>Batch Collisions</button>
        </div>
      </div>

      {tab === "scores" && <TrustScoresTab />}
      {tab === "collisions" && <BatchCollisionsTab />}

      <style>{`
        .trust-table { width: 100%; border-collapse: collapse; }
        .trust-table th, .trust-table td { text-align: left; padding: 10px; border-bottom: 1px solid #f0f0f0; }
        .trust-table th { color: #555; font-size: 13px; font-weight: 600; background: #fdfdfd; }
        .trust-detail-pane { background: #fafafa; padding: 16px; border-radius: 8px; margin: 8px; border: 1px solid #e5e5e5; }
        .trust-detail-pane h4 { margin: 0 0 8px 0; color: #333; font-size: 14px; }
      `}</style>
    </div>
  );
}
