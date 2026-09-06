import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ShieldAlert, ShieldCheck, SlidersHorizontal, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function NetworkIntegrity() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("open");
  const [scanning, setScanning] = useState(false);
  
  const [message, setMessage] = useState(null); // { type: 'success' | 'error', text: '' }

  useEffect(() => {
    loadAlerts();
  }, [statusFilter]);

  const loadAlerts = async () => {
    setLoading(true);
    try {
      const data = await api.getNetworkIntegrityAlerts(statusFilter);
      setAlerts(data);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to load network alerts' });
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (alertId, newStatus) => {
    try {
      await api.updateAlertStatus(alertId, newStatus);
      setMessage({ type: 'success', text: `Alert marked as ${newStatus}` });
      loadAlerts();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || `Failed to mark alert as ${newStatus}` });
    }
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await api.triggerCollisionScan();
      setMessage({ type: 'success', text: "Cross-tenant scan triggered. Refreshing alerts..." });
      // auto refresh after scan
      setTimeout(() => {
        loadAlerts();
      }, 1500);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to trigger scan' });
    } finally {
      setScanning(false);
    }
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
        .header-section { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 16px; }
        .header-section h2 { margin: 0; color: var(--text-main); display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 24px; }
        
        .filters-row { display: flex; gap: 12px; align-items: center; margin-bottom: 24px; }
        select.custom-select { padding: 10px 16px; font-size: 14px; font-weight: 500; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-surface); color: var(--text-main); outline: none; cursor: pointer; transition: all 0.2s; }
        select.custom-select:hover { border-color: var(--text-muted); }
        select.custom-select:focus { border-color: var(--primary-500); box-shadow: 0 0 0 2px var(--primary-50); }
        
        .inline-alert { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-radius: 8px; margin-bottom: 24px; font-size: 14px; font-weight: 500; display: flex; gap: 10px; }
        .inline-alert.error { background-color: var(--danger-50, #fef2f2); border: 1px solid var(--danger-200, #fecaca); color: var(--danger-700, #b91c1c); }
        .inline-alert.success { background-color: var(--success-50, #f0fdf4); border: 1px solid var(--success-200, #bbf7d0); color: var(--success-700, #15803d); }
        .close-alert-btn { background: none; border: none; font-size: 18px; line-height: 1; cursor: pointer; color: inherit; opacity: 0.5; transition: opacity 0.2s; }
        .close-alert-btn:hover { opacity: 1; }

        .alerts-grid { display: flex; flex-direction: column; gap: 16px; }
        .alert-card { background: var(--bg-surface); padding: 20px; border-radius: 12px; border: 1px solid var(--border-color); display: flex; flex-direction: column; gap: 16px; transition: all 0.2s; }
        .alert-card:hover { border-color: var(--danger-300, #fca5a5); box-shadow: 0 4px 12px rgba(0,0,0,0.02); }
        
        .alert-card-header { display: flex; justify-content: space-between; align-items: flex-start; }
        .alert-med-title { font-weight: 700; font-size: 18px; color: var(--text-main); display: flex; align-items: center; gap: 8px; }
        .alert-batch-badge { background: var(--bg-app); padding: 4px 8px; border-radius: 6px; font-family: monospace; font-size: 14px; border: 1px solid var(--border-color); color: var(--text-main); }
        
        .alert-stats-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; font-size: 14px; color: var(--text-muted); }
        .stat-box { background: var(--bg-app); padding: 12px 16px; border-radius: 8px; border: 1px solid var(--border-color); }
        .stat-box strong { color: var(--text-main); font-size: 16px; display: block; margin-bottom: 2px; }
        
        .distributors-box { font-size: 13px; color: var(--text-muted); padding: 10px 14px; background: var(--warning-50, #fffbeb); border: 1px dashed var(--warning-300, #fcd34d); border-radius: 8px; display: flex; gap: 8px; align-items: flex-start; }
        
        .alert-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; border-top: 1px solid var(--border-color); padding-top: 16px; }
        
        .empty-state { padding: 60px 20px; text-align: center; background: var(--bg-surface); border: 1px dashed var(--border-color); border-radius: 12px; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; gap: 12px; }
      `}</style>

      <div className="header-section">
        <h2>
          <ShieldAlert size={28} style={{ color: "var(--danger-500, #ef4444)" }} />
          Network Integrity Alerts
        </h2>
        <div className="filters-row" style={{ margin: 0 }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="custom-select"
          >
            <option value="open">Status: Open Alerts</option>
            <option value="reviewed">Status: Reviewed</option>
            <option value="dismissed">Status: Dismissed</option>
          </select>
          <button
            className="btn btn-primary"
            onClick={handleScan}
            disabled={scanning}
            style={{ display: "flex", alignItems: "center", gap: "8px" }}
          >
            <SlidersHorizontal size={18} />
            {scanning ? "Scanning..." : "Force Scan Now"}
          </button>
        </div>
      </div>
      
      <p style={{ color: "var(--text-muted)", fontSize: "15px", marginBottom: "24px", marginTop: "-16px" }}>
        Detects counterfeit or grey-market batches crossing multi-tenant boundaries. We monitor the network to see if the same batch appears in multiple isolated pharmacies supplied by different distributors.
      </p>

      <AnimatePresence>
        {message && (
          <motion.div 
            initial={{ opacity: 0, height: 0, marginBottom: 0 }} 
            animate={{ opacity: 1, height: 'auto', marginBottom: 24 }} 
            exit={{ opacity: 0, height: 0, marginBottom: 0 }}
            className={`inline-alert ${message.type}`}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {message.type === 'error' ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
              {message.text}
            </div>
            <button className="close-alert-btn" onClick={() => setMessage(null)}>✖</button>
          </motion.div>
        )}
      </AnimatePresence>

      {loading ? (
        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "40px 0", display: "flex", justifyContent: "center", alignItems: "center", gap: "8px" }}>
           Loading network alerts...
        </div>
      ) : alerts.length === 0 ? (
        <motion.div 
            className="empty-state"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
        >
          <ShieldCheck style={{ width: "56px", height: "56px", color: "var(--success-500, #22c55e)" }} />
          <h3 style={{ margin: 0, fontSize: "18px", fontWeight: 600, color: "var(--text-main)" }}>
            No {statusFilter} alerts found
          </h3>
          <p style={{ margin: 0, maxWidth: "400px" }}>
            Your supply chain appears clean across the network. No batch collisions were detected.
          </p>
        </motion.div>
      ) : (
        <div className="alerts-grid">
          <AnimatePresence>
            {alerts.map((alert) => (
              <motion.div 
                key={alert.id} 
                className="alert-card"
                initial={{ opacity: 0, scale: 0.98 }} 
                animate={{ opacity: 1, scale: 1 }} 
                exit={{ opacity: 0, height: 0, marginTop: 0, padding: 0, overflow: "hidden" }}
                transition={{ duration: 0.2 }}
              >
                <div className="alert-card-header">
                  <div className="alert-med-title">
                    {alert.medicine_name}
                    <span className="alert-batch-badge">Batch: {alert.normalized_batch_no}</span>
                  </div>
                  <span
                    style={{
                      padding: "4px 10px", fontSize: "12px", fontWeight: 700, borderRadius: "6px", textTransform: "uppercase", letterSpacing: "0.5px",
                      backgroundColor: alert.severity === 'high' ? 'var(--danger-50)' : 'var(--warning-50)',
                      color: alert.severity === 'high' ? 'var(--danger-700)' : 'var(--warning-700)',
                      border: `1px solid ${alert.severity === 'high' ? 'var(--danger-200)' : 'var(--warning-200)'}`
                    }}
                  >
                    {alert.severity} Risk
                  </span>
                </div>
                
                <div className="alert-stats-row">
                  <div className="stat-box">
                    <strong>{alert.other_pharmacies_involved}</strong>
                    Other pharmacies involved in the network
                  </div>
                  <div className="stat-box">
                    <strong>{alert.occurrence_count}</strong>
                    Total sightings across all bills
                  </div>
                </div>
                
                <div className="distributors-box">
                  <Info size={16} style={{ flexShrink: 0, marginTop: "2px", color: "var(--warning-600)" }} />
                  <div>
                    <strong style={{ color: "var(--warning-700)" }}>Distributors linked to this batch globally:</strong>
                    <div style={{ marginTop: "4px" }}>{alert.distributor_names.join(', ')}</div>
                  </div>
                </div>
                
                {alert.status === 'open' && (
                  <div className="alert-actions">
                    <button
                      className="btn"
                      onClick={() => handleUpdateStatus(alert.id, 'dismissed')}
                      style={{ color: "var(--danger-600)" }}
                    >
                      Dismiss False Alarm
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleUpdateStatus(alert.id, 'reviewed')}
                    >
                      Mark as Reviewed & Investigated
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
