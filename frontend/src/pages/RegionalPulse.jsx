import React, { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity, AlertCircle, ArrowDownRight, ArrowRight, ArrowUpRight,
  CheckCircle2, EyeOff, Globe2, LockKeyhole, RefreshCw, ShieldCheck,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const LEVEL_ORDER = { stable: 0, watch: 1, elevated: 2, critical: 3 };
const SHAPE_BY_LEVEL = { stable: "●", watch: "◆", elevated: "▲", critical: "⬢" };
const TREND_ICON = { up: ArrowUpRight, down: ArrowDownRight, stable: ArrowRight };

const bandClass = (level) => `pulse-band pulse-band--${level || "stable"}`;

function PrivacyBadge({ minContributors }) {
  return (
    <div className="pulse-privacy-badge" role="note">
      <ShieldCheck size={15} aria-hidden="true" />
      <span>
        <strong>Privacy protected</strong>
        <small>At least {minContributors} pharmacies required</small>
      </span>
    </div>
  );
}

function SignalLegend() {
  return (
    <div className="pulse-legend" aria-label="Signal legend">
      {Object.keys(LEVEL_ORDER).map((level) => (
        <span className="pulse-legend-item" key={level}>
          <i className={bandClass(level)} aria-hidden="true" />
          <span>{level}</span>
          <b>{SHAPE_BY_LEVEL[level]}</b>
        </span>
      ))}
      <span className="pulse-legend-item">
        <i className="pulse-band pulse-band--suppressed" aria-hidden="true" />
        <span>hidden by privacy rule</span>
        <b><EyeOff size={11} /></b>
      </span>
    </div>
  );
}

function HeatmapTooltip({ cell }) {
  const TrendIcon = TREND_ICON[cell.trend] || ArrowRight;
  return (
    <div className="pulse-tooltip" role="tooltip">
      <strong>{cell.condition_name} · {cell.region_label}</strong>
      <span className={bandClass(cell.signal_level)}>
        {SHAPE_BY_LEVEL[cell.signal_level]} {cell.signal_level}
        <TrendIcon size={13} />
      </span>
      <span>{cell.contributor_count} contributing pharmacies</span>
      <span>Volume: {cell.public_volume_band.replace(" ", "-")}</span>
      <small>No shop, customer, or medicine identity is shown.</small>
    </div>
  );
}

function HeatmapCell({ cell, onSelect }) {
  return (
    <button
      type="button"
      className={`pulse-cell ${bandClass(cell.signal_level)}`}
      onClick={() => onSelect(cell)}
      aria-label={`${cell.condition_name} in ${cell.region_label}: ${cell.signal_level}`}
    >
      <div className="pulse-cell-top">
        <span className="pulse-cell-condition">{cell.condition_name}</span>
        <span className="pulse-cell-shape" aria-hidden="true">{SHAPE_BY_LEVEL[cell.signal_level]}</span>
      </div>
      <strong>{cell.signal_level}</strong>
      <span className="pulse-cell-meta">
        {cell.contributor_count} pharmacies · {cell.trend}
      </span>
      <div className="pulse-sparkline" aria-hidden="true">
        {cell.trend_labels.map((label, index) => (
          <i key={index} className={bandClass(label)} style={{ height: `${8 + LEVEL_ORDER[label] * 5}px` }} />
        ))}
      </div>
      <HeatmapTooltip cell={cell} />
    </button>
  );
}

function SuppressedCell({ suppressedCells }) {
  return (
    <div className="pulse-cell pulse-cell--suppressed" role="note">
      <EyeOff size={18} />
      <strong>Hidden to protect privacy</strong>
      <span>{suppressedCells} cell{suppressedCells === 1 ? "" : "s"} below the 3-pharmacy rule</span>
    </div>
  );
}

export default function RegionalPulse() {
  const { isOwner } = useAuth();
  const [data, setData] = useState(null);
  const [regionDetail, setRegionDetail] = useState(null);
  const [selectedCell, setSelectedCell] = useState(null);
  const [condition, setCondition] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState(null);

  const loadHeatmap = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.getRegionalHeatmap(condition ? { condition_name: condition } : {});
      setData(result);
      setMessage(null);
    } catch (error) {
      setMessage({ type: "error", text: error.message || "Unable to load regional pulse." });
    } finally {
      setLoading(false);
    }
  }, [condition]);

  useEffect(() => { loadHeatmap(); }, [loadHeatmap]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.refreshRegionalHeatmap();
      await loadHeatmap();
      setMessage({ type: "success", text: "Heatmap rebuilt. Privacy rule verified." });
    } catch (error) {
      setMessage({ type: "error", text: error.message || "Unable to refresh heatmap." });
    } finally {
      setRefreshing(false);
    }
  };

  const handleCellSelect = async (cell) => {
    setSelectedCell(cell);
    try {
      setRegionDetail(await api.getRegionHeatmap(cell.region_code));
    } catch {
      setRegionDetail(null);
    }
  };

  const cells = useMemo(() => {
    return (data?.cells || []).map((cell) => ({
      ...cell,
      region_label: cell.region_code.replace(/^[A-Z]{2}-/, "").replace(/-/g, " "),
    }));
  }, [data]);

  const grouped = useMemo(() => {
    const map = new Map();
    cells.forEach((cell) => {
      const key = `${cell.region_code}:${cell.condition_name}`;
      map.set(key, cell);
    });
    return Array.from(map.values());
  }, [cells]);

  const conditions = useMemo(
    () => Array.from(new Set(cells.map((cell) => cell.condition_name))).sort(),
    [cells]
  );

  return (
    <motion.div className="page-content pulse-page" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
      <style>{`
        .pulse-page{--pulse-ink:#0f172a;--pulse-teal:#0f766e;--pulse-muted:#64748b;color:var(--pulse-ink);max-width:1280px;margin:0 auto;padding:8px 4px 40px}
        .pulse-hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;padding:28px 30px;border-radius:20px;color:#fff;background:radial-gradient(circle at 85% 15%,#14b8a6 0,#0f766e 42%,#115e59 100%);box-shadow:0 18px 40px rgba(15,118,110,.22)}
        .pulse-hero h1{font-size:27px;margin:0 0 6px;font-weight:750;letter-spacing:-.02em}
        .pulse-hero p{margin:0;opacity:.9;font-size:14px;max-width:620px}
        .pulse-hero-tag{display:inline-flex;align-items:center;gap:7px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:7px 12px;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
        .pulse-toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin:22px 0 14px}
        .pulse-filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
        .pulse-select{background:#fff;border:1px solid #cbd5e1;border-radius:10px;padding:9px 12px;color:var(--pulse-ink);font-size:13px;min-width:180px}
        .pulse-btn{border:0;border-radius:10px;padding:10px 15px;font-size:13px;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;gap:8px;transition:.18s}
        .pulse-btn:disabled{opacity:.6;cursor:not-allowed}
        .pulse-btn--primary{background:var(--pulse-teal);color:#fff}
        .pulse-btn--primary:hover:not(:disabled){background:#0d5f58;transform:translateY(-1px)}
        .pulse-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
        .pulse-cell{position:relative;text-align:left;min-height:150px;padding:17px;background:#fff;border:1px solid #e2e8f0;border-left:5px solid var(--band-color);border-radius:14px;cursor:pointer;display:flex;flex-direction:column;gap:7px;box-shadow:0 4px 14px rgba(15,23,42,.04);transition:.2s}
        .pulse-cell:hover{transform:translateY(-3px);box-shadow:0 12px 24px rgba(15,23,42,.09)}
        .pulse-cell strong{font-size:16px;text-transform:capitalize}
        .pulse-cell-condition{font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--pulse-muted)}
        .pulse-cell-top{display:flex;justify-content:space-between;align-items:center}
        .pulse-cell-shape{font-size:18px;color:var(--band-color)}
        .pulse-cell-meta{font-size:12px;color:var(--pulse-muted)}
        .pulse-sparkline{display:flex;gap:3px;align-items:flex-end;height:22px;margin-top:auto}
        .pulse-sparkline i{width:11px;border-radius:2px 2px 0 0;background:var(--band-color);opacity:${0.4};display:block}
        .pulse-sparkline i.pulse-band--suppressed{background:#cbd5e1}
        .pulse-band--stable{--band-color:#0f766e;color:#0f766e}
        .pulse-band--watch{--band-color:#d97706;color:#d97706}
        .pulse-band--elevated{--band-color:#dc2626;color:#dc2626}
        .pulse-band--critical{--band-color:#991b1b;color:#991b1b}
        .pulse-band--suppressed{--band-color:#94a3b8;color:#64748b}
        .pulse-cell--suppressed{cursor:default;border-left-color:#94a3b8;background:repeating-linear-gradient(45deg,#f8fafc,#f8fafc 9px,#eef2f7 9px,#eef2f7 18px)}
        .pulse-cell--suppressed strong{font-size:14px;color:#475569}
        .pulse-tooltip{position:absolute;left:16px;right:16px;bottom:calc(100% + 8px);z-index:5;display:none;flex-direction:column;gap:5px;padding:12px;border-radius:10px;background:#0f172a;color:#e2e8f0;font-size:12px;box-shadow:0 10px 24px rgba(15,23,42,.25);pointer-events:none}
        .pulse-tooltip span{display:flex;align-items:center;gap:6px}
        .pulse-tooltip small{color:#94a3b8;line-height:1.4}
        .pulse-cell:hover .pulse-tooltip,.pulse-cell:focus-within .pulse-tooltip{display:flex}
        .pulse-tooltip .pulse-band{color:currentColor}
        .pulse-card{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:20px;margin-top:18px}
        .pulse-card h3{margin:0 0 12px;font-size:16px}
        .pulse-insight{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
        .pulse-insight-item{background:#f8fafc;border-radius:10px;padding:12px}
        .pulse-insight-item span{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--pulse-muted)}
        .pulse-insight-item strong{font-size:14px;text-transform:capitalize}
        .pulse-privacy-badge{display:inline-flex;align-items:center;gap:9px;border:1px solid #99f6e4;background:#f0fdfa;color:#0f766e;border-radius:12px;padding:9px 13px}
        .pulse-privacy-badge span{display:flex;flex-direction:column;line-height:1.25}
        .pulse-privacy-badge small{color:#0f766e;opacity:.8}
        .pulse-legend{display:flex;flex-wrap:wrap;gap:14px;align-items:center;font-size:11px;color:var(--pulse-muted)}
        .pulse-legend-item{display:inline-flex;align-items:center;gap:5px}
        .pulse-legend-item i{width:9px;height:9px;border-radius:3px;background:var(--band-color);display:inline-block}
        .pulse-legend-item b{color:var(--band-color)}
        .pulse-notice{margin-top:16px;display:flex;gap:9px;align-items:flex-start;font-size:12px;color:var(--pulse-muted)}
        .pulse-empty{padding:48px 20px;text-align:center;background:#fff;border:1px dashed #cbd5e1;border-radius:16px;color:var(--pulse-muted)}
        .pulse-empty h3{color:var(--pulse-ink);margin:10px 0 5px}
      `}</style>

      <header className="pulse-hero">
        <div>
          <span className="pulse-hero-tag"><Globe2 size={13} /> Regional Pulse · PharmOs Shield</span>
          <h1>See the signal. Never the person.</h1>
          <p>
            Privacy-preserving public-health signals from opted-in pharmacies. Aggregated by region and condition,
            published only when at least three pharmacies contribute.
          </p>
        </div>
        <PrivacyBadge minContributors={data?.privacy?.min_contributors || 3} />
      </header>

      {message && (
        <div className={`pulse-notice ${message.type === "error" ? "" : "pulse-success"}`} role="status">
          {message.type === "error" ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}
          <span>{message.text}</span>
        </div>
      )}

      <div className="pulse-toolbar">
        <div className="pulse-filters">
          <select
            className="pulse-select"
            value={condition}
            onChange={(event) => setCondition(event.target.value)}
            aria-label="Filter by condition"
          >
            <option value="">All conditions</option>
            {conditions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          {isOwner && (
            <button className="pulse-btn pulse-btn--primary" onClick={handleRefresh} disabled={refreshing}>
              <RefreshCw size={15} className={refreshing ? "spin" : ""} />
              {refreshing ? "Rebuilding…" : "Refresh snapshot"}
            </button>
          )}
        </div>
        <SignalLegend />
      </div>

      {loading ? (
        <div className="pulse-empty"><RefreshCw className="spin" /> Computing regional signals…</div>
      ) : grouped.length === 0 ? (
        <div className="pulse-empty">
          <LockKeyhole size={28} />
          <h3>Not enough contributions yet</h3>
          <p>
            {data?.suppressed_cells
              ? `${data.suppressed_cells} cell(s) are hidden to protect privacy until 3 pharmacies contribute.`
              : "No opted-in regional signals are available for this window."}
          </p>
        </div>
      ) : (
        <div className="pulse-grid" data-testid="heatmap-grid">
          {grouped.map((cell) => <HeatmapCell key={`${cell.region_code}:${cell.condition_name}`} cell={cell} onSelect={handleCellSelect} />)}
          {data?.suppressed_cells > 0 && <SuppressedCell suppressedCells={data.suppressed_cells} />}
        </div>
      )}

      {selectedCell && (
        <section className="pulse-card" aria-label="Insight drawer">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <h3><Activity size={16} style={{ verticalAlign: "middle" }} /> {selectedCell.condition_name} in {selectedCell.region_label}</h3>
            <PrivacyBadge minContributors={data?.privacy?.min_contributors || 3} />
          </div>
          <div className="pulse-insight">
            <div className="pulse-insight-item"><span>Signal</span><strong className={bandClass(selectedCell.signal_level)}>{SHAPE_BY_LEVEL[selectedCell.signal_level]} {selectedCell.signal_level}</strong></div>
            <div className="pulse-insight-item"><span>Contributors</span><strong>{selectedCell.contributor_count} pharmacies</strong></div>
            <div className="pulse-insight-item"><span>Window</span><strong>{data?.window_days || 7} days</strong></div>
            <div className="pulse-insight-item"><span>Confidence</span><strong>{selectedCell.confidence}</strong></div>
          </div>
          {regionDetail && <p style={{ fontSize: 12, color: "#64748b", marginBottom: 0 }}>
            {regionDetail.cells.length} sanitized condition cell(s) available for this region.
          </p>}
        </section>
      )}

      <p className="pulse-notice">
        <ShieldCheck size={15} />
        <span>{data?.notice || "Public-health signal for awareness only; not a medical diagnosis."}</span>
      </p>
    </motion.div>
  );
}
