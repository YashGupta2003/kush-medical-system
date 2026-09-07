import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import {
  ActivitySquare, AlertTriangle, CheckCircle2, Globe, Info,
  MapPin, RefreshCw, Settings, ShieldCheck, SlidersHorizontal
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function RegionalHealth() {
  const { isOwner } = useAuth();

  const [alerts, setAlerts] = useState([]);
  const [participation, setParticipation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('open');
  const [scanning, setScanning] = useState(false);
  const [savingPart, setSavingPart] = useState(false);
  const [message, setMessage] = useState(null);

  // Participation form state (owner only)
  const [regionInput, setRegionInput] = useState('');
  const [optInInput, setOptInInput] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    loadAll();
  }, [statusFilter]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [part, alertsData] = await Promise.all([
        api.getRegionalParticipation(),
        api.getRegionalHealthAlerts(statusFilter),
      ]);
      setParticipation(part);
      setRegionInput(part.region_code || '');
      setOptInInput(!!part.surveillance_opt_in);
      setAlerts(alertsData);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to load regional health data' });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveParticipation = async () => {
    setSavingPart(true);
    try {
      const updated = await api.updateRegionalParticipation(regionInput || null, optInInput);
      setParticipation(updated);
      setMessage({ type: 'success', text: 'Regional participation settings saved.' });
      setShowSettings(false);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to save participation settings.' });
    } finally {
      setSavingPart(false);
    }
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await api.triggerRegionalScan();
      setMessage({ type: 'success', text: 'Regional health scan queued. Refreshing alerts shortly...' });
      setTimeout(() => loadAll(), 2000);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to trigger scan.' });
    } finally {
      setScanning(false);
    }
  };

  const handleUpdateAlertStatus = async (alertId, newStatus) => {
    try {
      await api.updateRegionalAlertStatus(alertId, newStatus);
      setMessage({ type: 'success', text: `Alert marked as ${newStatus}.` });
      loadAll();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || `Failed to update alert status.` });
    }
  };

  const severityStyle = (sev) => {
    if (sev === 'critical') return {
      background: 'var(--danger-bg)',
      color: 'var(--danger-text)',
      border: '1px solid var(--danger-border)',
    };
    if (sev === 'elevated') return {
      background: 'var(--warning-bg)',
      color: 'var(--warning-text)',
      border: '1px solid var(--warning-border)',
    };
    return {
      background: 'var(--info-bg)',
      color: 'var(--info-text)',
      border: '1px solid var(--info-border)',
    };
  };

  return (
    <motion.div
      className="page-content"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
    >
      <style>{`
        .rh-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 16px; }
        .rh-header h2 { margin: 0; color: var(--text-main); display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 24px; }

        .rh-participation-card { background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 20px; margin-bottom: 24px; display: flex; flex-direction: column; gap: 12px; }
        .rh-participation-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
        .rh-opt-in-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 700; }
        .rh-opt-in-badge.on { background: var(--success-bg); color: var(--success-text); border: 1px solid var(--success-border); }
        .rh-opt-in-badge.off { background: var(--danger-bg); color: var(--danger-text); border: 1px solid var(--danger-border); }

        .rh-settings-form { display: flex; flex-direction: column; gap: 12px; margin-top: 12px; padding-top: 16px; border-top: 1px solid var(--border-subtle); }
        .rh-settings-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
        .rh-input { padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border-strong); background: var(--bg-app); color: var(--text-main); font-size: 14px; font-weight: 500; outline: none; min-width: 220px; transition: border-color 0.2s; }
        .rh-input:focus { border-color: var(--primary-500); box-shadow: 0 0 0 2px var(--primary-50); }
        .rh-checkbox-row { display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }
        .rh-checkbox-row input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--primary-500); cursor: pointer; }

        .rh-filters-row { display: flex; gap: 12px; align-items: center; margin-bottom: 24px; flex-wrap: wrap; }
        .rh-select { padding: 10px 16px; font-size: 14px; font-weight: 500; border-radius: 8px; border: 1px solid var(--border-strong); background: var(--bg-surface); color: var(--text-main); outline: none; cursor: pointer; transition: all 0.2s; }
        .rh-select:hover { border-color: var(--text-muted); }

        .rh-inline-alert { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-radius: 8px; margin-bottom: 24px; font-size: 14px; font-weight: 500; gap: 10px; }
        .rh-inline-alert.error { background: var(--danger-bg); border: 1px solid var(--danger-border); color: var(--danger-text); }
        .rh-inline-alert.success { background: var(--success-bg); border: 1px solid var(--success-border); color: var(--success-text); }
        .rh-close-btn { background: none; border: none; font-size: 18px; line-height: 1; cursor: pointer; color: inherit; opacity: 0.5; transition: opacity 0.2s; }
        .rh-close-btn:hover { opacity: 1; }

        .rh-alerts-grid { display: flex; flex-direction: column; gap: 16px; }
        .rh-alert-card { background: var(--bg-surface); padding: 20px; border-radius: 12px; border: 1px solid var(--border-subtle); display: flex; flex-direction: column; gap: 16px; transition: all 0.2s; }
        .rh-alert-card:hover { border-color: var(--primary-500); box-shadow: 0 4px 12px rgba(0,0,0,0.04); }
        .rh-alert-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
        .rh-alert-title { font-weight: 700; font-size: 18px; color: var(--text-main); display: flex; align-items: center; gap: 8px; }
        .rh-alert-date { font-size: 13px; color: var(--text-muted); }

        .rh-stats-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
        .rh-stat-box { background: var(--bg-app); padding: 12px 14px; border-radius: 8px; border: 1px solid var(--border-subtle); }
        .rh-stat-box strong { display: block; font-size: 20px; font-weight: 700; color: var(--text-main); margin-bottom: 2px; }
        .rh-stat-box span { font-size: 12px; color: var(--text-muted); }

        .rh-info-box { font-size: 13px; color: var(--info-text); padding: 10px 14px; background: var(--info-bg); border: 1px solid var(--info-border); border-radius: 8px; display: flex; gap: 8px; align-items: flex-start; }
        .rh-info-icon { flex-shrink: 0; margin-top: 2px; }

        .rh-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; border-top: 1px solid var(--border-subtle); padding-top: 16px; }

        .rh-empty { padding: 60px 20px; text-align: center; background: var(--bg-surface); border: 1px dashed var(--border-strong); border-radius: 12px; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; gap: 12px; }

        .rh-sev-pill { padding: 4px 10px; font-size: 12px; font-weight: 700; border-radius: 6px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }
      `}</style>

      {/* Header */}
      <div className="rh-header">
        <h2>
          <ActivitySquare size={28} style={{ color: 'var(--primary-500)' }} />
          Regional Health Sentinel
        </h2>
        <div className="rh-filters-row" style={{ margin: 0 }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rh-select"
          >
            <option value="open">Status: Open</option>
            <option value="acknowledged">Status: Acknowledged</option>
            <option value="dismissed">Status: Dismissed</option>
          </select>
          {isOwner && (
            <>
              <button className="btn" onClick={() => setShowSettings((s) => !s)}>
                <Settings size={16} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                Participation
              </button>
              <button className="btn btn-primary" onClick={handleScan} disabled={scanning}>
                <SlidersHorizontal size={16} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                {scanning ? 'Scanning...' : 'Force Scan Now'}
              </button>
            </>
          )}
        </div>
      </div>

      <p style={{ color: 'var(--text-muted)', fontSize: '15px', marginBottom: '24px', marginTop: '-16px' }}>
        Aggregates opted-in, privacy-safe OTC daily counts across pharmacies sharing the same region
        code to surface cross-pharmacy disease early-warning signals. Individual pharmacy counts and
        identities are never exposed — only regional totals.
      </p>

      {/* Inline message */}
      <AnimatePresence>
        {message && (
          <motion.div
            initial={{ opacity: 0, height: 0, marginBottom: 0 }}
            animate={{ opacity: 1, height: 'auto', marginBottom: 24 }}
            exit={{ opacity: 0, height: 0, marginBottom: 0 }}
            className={`rh-inline-alert ${message.type}`}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {message.type === 'error' ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
              {message.text}
            </div>
            <button className="rh-close-btn" onClick={() => setMessage(null)}>✖</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Participation panel (owner only, collapsible) */}
      {participation !== null && (
        <div className="rh-participation-card">
          <div className="rh-participation-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Globe size={20} style={{ color: 'var(--primary-500)' }} />
              <div>
                <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                  Regional Participation
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  {participation.region_code
                    ? (<><MapPin size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} />{participation.region_code}</>)
                    : 'No region set'}
                </div>
              </div>
            </div>
            <span className={`rh-opt-in-badge ${participation.surveillance_opt_in ? 'on' : 'off'}`}>
              {participation.surveillance_opt_in ? '✓ Opted In' : '✗ Opted Out'}
            </span>
          </div>

          <AnimatePresence>
            {isOwner && showSettings && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="rh-settings-form"
              >
                <div className="rh-settings-row">
                  <input
                    className="rh-input"
                    placeholder="Region code (e.g. MUMBAI, DELHI, 400001)"
                    value={regionInput}
                    onChange={(e) => setRegionInput(e.target.value)}
                  />
                  <label className="rh-checkbox-row">
                    <input
                      type="checkbox"
                      checked={optInInput}
                      onChange={(e) => setOptInInput(e.target.checked)}
                    />
                    <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-main)' }}>
                      Opt in to regional surveillance
                    </span>
                  </label>
                  <button className="btn btn-primary" onClick={handleSaveParticipation} disabled={savingPart}>
                    {savingPart ? 'Saving...' : 'Save'}
                  </button>
                  <button className="btn" onClick={() => setShowSettings(false)}>Cancel</button>
                </div>
                <div className="rh-info-box">
                  <Info size={15} className="rh-info-icon" />
                  <span>
                    Your daily OTC counts will be included in regional aggregates shared with other
                    opted-in pharmacies in the same region. Individual sale data and customer
                    information are NEVER shared — only privacy-safe daily totals per condition.
                  </span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Alert display */}
      {loading ? (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 0' }}>
          Loading regional health alerts...
        </div>
      ) : !participation?.surveillance_opt_in ? (
        <motion.div className="rh-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Globe style={{ width: 56, height: 56, color: 'var(--text-muted)' }} />
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: 'var(--text-main)' }}>
            Regional surveillance not active
          </h3>
          <p style={{ margin: 0, maxWidth: 440 }}>
            {isOwner
              ? 'Use the Participation panel above to opt in and set your region code. Your pharmacy\'s OTC daily counts will then be aggregated with other opted-in pharmacies for early disease detection.'
              : 'Your pharmacy has not opted in to regional surveillance. Ask the owner to enable it in Regional Health → Participation.'}
          </p>
        </motion.div>
      ) : alerts.length === 0 ? (
        <motion.div className="rh-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <ShieldCheck style={{ width: 56, height: 56, color: 'var(--success-text)' }} />
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: 'var(--text-main)' }}>
            No {statusFilter} regional alerts
          </h3>
          <p style={{ margin: 0, maxWidth: 440 }}>
            No statistically unusual disease pattern has been detected in your region in the current window.
          </p>
        </motion.div>
      ) : (
        <div className="rh-alerts-grid">
          <AnimatePresence>
            {alerts.map((alert) => (
              <motion.div
                key={alert.id}
                className="rh-alert-card"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, height: 0, marginTop: 0, padding: 0, overflow: 'hidden' }}
                transition={{ duration: 0.2 }}
              >
                <div className="rh-alert-header">
                  <div className="rh-alert-title">
                    <ActivitySquare size={22} style={{ color: 'var(--primary-500)' }} />
                    {alert.condition_name}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                    <span className="rh-sev-pill" style={severityStyle(alert.severity)}>
                      {alert.severity}
                    </span>
                    <div className="rh-alert-date">
                      {alert.alert_date}
                    </div>
                  </div>
                </div>

                <div className="rh-stats-grid">
                  <div className="rh-stat-box">
                    <strong>{alert.contributing_tenant_count}</strong>
                    <span>Pharmacies reporting spike</span>
                  </div>
                  <div className="rh-stat-box">
                    <strong>{alert.total_regional_units}</strong>
                    <span>Combined units sold that day</span>
                  </div>
                  <div className="rh-stat-box">
                    <strong>{alert.z_score.toFixed(2)}</strong>
                    <span>Z-score vs. regional baseline</span>
                  </div>
                </div>

                <div className="rh-info-box">
                  <Info size={15} className="rh-info-icon" />
                  <span>
                    Regional baseline avg: {alert.regional_avg_units.toFixed(1)} units/day.
                    Combined sales on {alert.alert_date} were {alert.total_regional_units} units —
                    a {alert.z_score.toFixed(1)}σ spike. No individual pharmacy counts or
                    identities are shared.
                  </span>
                </div>

                {isOwner && alert.status === 'open' && (
                  <div className="rh-actions">
                    <button
                      className="btn"
                      style={{ color: 'var(--danger-text)' }}
                      onClick={() => handleUpdateAlertStatus(alert.id, 'dismissed')}
                    >
                      Dismiss
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleUpdateAlertStatus(alert.id, 'acknowledged')}
                    >
                      Acknowledge &amp; Investigate
                    </button>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}

function severityStyle(sev) {
  if (sev === 'critical') return {
    background: 'var(--danger-bg)',
    color: 'var(--danger-text)',
    border: '1px solid var(--danger-border)',
  };
  if (sev === 'elevated') return {
    background: 'var(--warning-bg)',
    color: 'var(--warning-text)',
    border: '1px solid var(--warning-border)',
  };
  return {
    background: 'var(--info-bg)',
    color: 'var(--info-text)',
    border: '1px solid var(--info-border)',
  };
}
