import React, { useState, useEffect } from "react";
import { api } from "../api/client";
import { AreaChart, Area, BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";
import { Snowflake, FileText, Monitor, CheckSquare, Bell, Plus, CheckCircle, AlertTriangle, Info } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function ColdChain({ isOwner }) {
    const [activeTab, setActiveTab] = useState("log");
    
    // Log Tab
    const [units, setUnits] = useState([]);
    const [selectedUnit, setSelectedUnit] = useState("");
    const [temp, setTemp] = useState("");
    const [note, setNote] = useState("");
    const [recentReadings, setRecentReadings] = useState([]);
    const [logStatus, setLogStatus] = useState(null);
    const [loading, setLoading] = useState(false);

    // Units Tab (Owner)
    const [newUnit, setNewUnit] = useState({ unit_label: "", location_note: "", min_temp_c: 2.0, max_temp_c: 8.0 });
    
    // Compliance Tab (Owner)
    const [complianceReport, setComplianceReport] = useState(null);
    const [complianceDays, setComplianceDays] = useState(30);

    // Alerts Tab (Owner)
    const [compromisedBatches, setCompromisedBatches] = useState([]);
    const [selectedCompUnit, setSelectedCompUnit] = useState("");

    useEffect(() => {
        loadUnits();
    }, []);

    useEffect(() => {
        if (selectedUnit) {
            loadReadings(selectedUnit);
        }
    }, [selectedUnit]);

    useEffect(() => {
        if (activeTab === "compliance" && isOwner) {
            loadCompliance();
        }
    }, [activeTab, complianceDays]);

    useEffect(() => {
        if (activeTab === "alerts" && isOwner && selectedCompUnit) {
            loadCompromisedBatches(selectedCompUnit);
        }
    }, [activeTab, selectedCompUnit]);

    const loadUnits = async () => {
        try {
            const data = await api.getColdChainUnits();
            setUnits(data);
            if (data.length > 0 && !selectedUnit) setSelectedUnit(data[0].id.toString());
            if (data.length > 0 && !selectedCompUnit) setSelectedCompUnit(data[0].id.toString());
        } catch (err) {
            console.error("Failed to load units:", err);
        }
    };

    const loadReadings = async (unitId) => {
        try {
            const data = await api.getColdChainReadings(unitId);
            setRecentReadings(data);
        } catch (err) {
            console.error("Failed to load readings:", err);
        }
    };

    const loadCompliance = async () => {
        try {
            const data = await api.getColdChainCompliance(complianceDays);
            setComplianceReport(data);
        } catch (err) {
            console.error("Failed to load compliance report:", err);
        }
    };

    const loadCompromisedBatches = async (unitId) => {
        try {
            const data = await api.getCompromisedBatches(unitId);
            setCompromisedBatches(data);
        } catch (err) {
            console.error("Failed to load compromised batches:", err);
        }
    };

    const handleLogReading = async (e) => {
        e.preventDefault();
        if (!selectedUnit) {
            setLogStatus({ type: "error", msg: "Please select a unit first. If none exist, ask the owner to create one." });
            return;
        }
        setLoading(true);
        try {
            await api.recordColdChainReading({
                unit_id: parseInt(selectedUnit),
                recorded_temp_c: parseFloat(temp),
                note: note
            });
            setTemp("");
            setNote("");
            setLogStatus({ type: "success", msg: "Reading logged successfully." });
            loadReadings(selectedUnit);
            setTimeout(() => setLogStatus(null), 3000);
        } catch (err) {
            setLogStatus({ type: "error", msg: "Failed to log reading." });
        } finally {
            setLoading(false);
        }
    };

    const handleCreateUnit = async (e) => {
        e.preventDefault();
        try {
            await api.createColdChainUnit(newUnit);
            setNewUnit({ unit_label: "", location_note: "", min_temp_c: 2.0, max_temp_c: 8.0 });
            loadUnits();
        } catch (err) {
            console.error(err);
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
                .cc-header { margin-bottom: var(--spacing-xl, 24px); display: flex; align-items: center; gap: 12px; }
                .cc-header h1 { margin: 0; font-size: 24px; color: var(--text-main); display: flex; align-items: center; gap: 8px; }
                .cc-header p { margin: 4px 0 0 32px; color: var(--text-muted); font-size: 14px; }
                
                .cc-tabs { display: flex; gap: 16px; margin-bottom: 24px; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; overflow-x: auto; }
                .cc-tab { background: none; border: none; padding: 8px 16px; font-weight: 500; color: var(--text-muted); cursor: pointer; border-radius: 6px; display: flex; align-items: center; gap: 8px; transition: all 0.2s; white-space: nowrap; }
                .cc-tab:hover { background: var(--bg-hover, rgba(0,0,0,0.05)); }
                .cc-tab.active { background: var(--primary-50, rgba(37, 99, 235, 0.1)); color: var(--primary-500); }
                
                .cc-form-group { margin-bottom: 16px; }
                .cc-form-group label { display: block; margin-bottom: 8px; font-weight: 500; font-size: 14px; color: var(--text-main); }
                .cc-input { width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; font-size: 14px; background: var(--bg-surface); color: var(--text-main); }
                .cc-input:focus { outline: 2px solid var(--primary-500); border-color: transparent; }
                
                .cc-reading-row { display: flex; justify-content: space-between; align-items: center; padding: 12px; border-bottom: 1px solid var(--border-color); }
                .cc-reading-row:last-child { border-bottom: none; }
                
                .cc-stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
                .cc-stat-card { background: var(--bg-surface); padding: 20px; border-radius: 8px; text-align: center; border: 1px solid var(--border-color); box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
                .cc-stat-val { font-size: 28px; font-weight: bold; color: var(--text-main); margin-bottom: 4px; }
                .cc-stat-lbl { font-size: 13px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
                
                .table { width: 100%; text-align: left; border-collapse: collapse; }
                .table th { padding: 12px; border-bottom: 2px solid var(--border-color); color: var(--text-muted); font-weight: 600; font-size: 14px; }
                .table td { padding: 12px; border-bottom: 1px solid var(--border-color); color: var(--text-main); font-size: 14px; }
            `}</style>

            <div className="cc-header">
                <div>
                    <h1><Snowflake className="icon" size={28} style={{ color: "var(--primary-500)" }} /> Cold-Chain Compliance</h1>
                    <p>Monitor fridge temperatures, detect excursions, and maintain regulatory compliance.</p>
                </div>
            </div>

            <div className="cc-tabs">
                <button className={`cc-tab ${activeTab === "log" ? "active" : ""}`} onClick={() => setActiveTab("log")}>
                    <FileText size={18} /> Log Reading
                </button>
                {isOwner && (
                    <>
                        <button className={`cc-tab ${activeTab === "units" ? "active" : ""}`} onClick={() => setActiveTab("units")}>
                            <Monitor size={18} /> Manage Units
                        </button>
                        <button className={`cc-tab ${activeTab === "compliance" ? "active" : ""}`} onClick={() => setActiveTab("compliance")}>
                            <CheckSquare size={18} /> Compliance Report
                        </button>
                        <button className={`cc-tab ${activeTab === "alerts" ? "active" : ""}`} onClick={() => setActiveTab("alerts")}>
                            <Bell size={18} /> Excursion Alerts
                        </button>
                    </>
                )}
            </div>

            <AnimatePresence mode="wait">
                <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    transition={{ duration: 0.15 }}
                >
                    {activeTab === "log" && (
                        <div className="card">
                            <h3 style={{ marginTop: 0, color: "var(--text-main)" }}>Record Temperature</h3>
                            <form onSubmit={handleLogReading} style={{ maxWidth: "400px", marginBottom: "32px" }}>
                                <div className="cc-form-group">
                                    <label>Select Unit</label>
                                    <select className="cc-input" value={selectedUnit} onChange={(e) => setSelectedUnit(e.target.value)} required disabled={units.length === 0}>
                                        {units.length === 0 && <option value="">No units configured</option>}
                                        {units.length > 0 && <option value="" disabled>Select a unit...</option>}
                                        {units.map(u => <option key={u.id} value={u.id}>{u.unit_label}</option>)}
                                    </select>
                                </div>
                                <div className="cc-form-group">
                                    <label>Temperature (°C)</label>
                                    <input type="number" step="0.1" className="cc-input" value={temp} onChange={(e) => setTemp(e.target.value)} required />
                                </div>
                                <div className="cc-form-group">
                                    <label>Note (Optional)</label>
                                    <input type="text" className="cc-input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="E.g. routine check" />
                                </div>
                                <button type="submit" className="btn btn-primary" disabled={loading || units.length === 0}>
                                    <Plus size={16} /> Log Reading
                                </button>
                                {logStatus && (
                                    <div style={{ marginTop: "12px", display: "flex", alignItems: "center", gap: 8, color: logStatus.type === "error" ? "var(--danger-500, #ef4444)" : "var(--success-500, #10b981)" }}>
                                        <Info size={16} /> {logStatus.msg}
                                    </div>
                                )}
                            </form>

                            <h3 style={{ color: "var(--text-main)" }}>Recent Readings (24h)</h3>
                            {recentReadings.length === 0 ? <p style={{ color: "var(--text-muted)" }}>No readings in the last 24 hours.</p> : (
                                <div style={{ border: "1px solid var(--border-color)", borderRadius: "8px", overflow: "hidden" }}>
                                    {recentReadings.map(r => (
                                        <div key={r.id} className="cc-reading-row">
                                            <div>
                                                <div style={{ fontWeight: 600, color: "var(--text-main)", fontSize: "16px" }}>{r.recorded_temp_c}°C</div>
                                                <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>{new Date(r.recorded_at).toLocaleString()} by {r.recorded_by_username || "System"}</div>
                                            </div>
                                            <div>
                                                {r.is_excursion ? 
                                                    <span className="badge badge-danger" style={{ display: "flex", alignItems: "center", gap: 4 }}><AlertTriangle size={12}/> Excursion</span> : 
                                                    <span className="badge badge-success" style={{ display: "flex", alignItems: "center", gap: 4 }}><CheckCircle size={12}/> Compliant</span>
                                                }
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {activeTab === "units" && isOwner && (
                        <div className="card">
                            <h3 style={{ marginTop: 0, color: "var(--text-main)" }}>Create New Unit</h3>
                            <form onSubmit={handleCreateUnit} style={{ maxWidth: "400px", marginBottom: "40px" }}>
                                <div className="cc-form-group">
                                    <label>Unit Label</label>
                                    <input type="text" className="cc-input" value={newUnit.unit_label} onChange={e => setNewUnit({...newUnit, unit_label: e.target.value})} placeholder="E.g. Main Fridge" required />
                                </div>
                                <div style={{ display: "flex", gap: "16px" }}>
                                    <div className="cc-form-group" style={{ flex: 1 }}>
                                        <label>Min Temp (°C)</label>
                                        <input type="number" step="0.1" className="cc-input" value={newUnit.min_temp_c} onChange={e => setNewUnit({...newUnit, min_temp_c: e.target.value})} required />
                                    </div>
                                    <div className="cc-form-group" style={{ flex: 1 }}>
                                        <label>Max Temp (°C)</label>
                                        <input type="number" step="0.1" className="cc-input" value={newUnit.max_temp_c} onChange={e => setNewUnit({...newUnit, max_temp_c: e.target.value})} required />
                                    </div>
                                </div>
                                <button type="submit" className="btn btn-primary"><Plus size={16} /> Create Unit</button>
                            </form>

                            <h3 style={{ color: "var(--text-main)" }}>Configured Units</h3>
                            <div style={{ overflowX: "auto" }}>
                                <table className="table">
                                    <thead>
                                        <tr>
                                            <th>Label</th>
                                            <th>Safe Range</th>
                                            <th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {units.map(u => (
                                            <tr key={u.id}>
                                                <td style={{ fontWeight: 500 }}>{u.unit_label}</td>
                                                <td>{u.min_temp_c}°C – {u.max_temp_c}°C</td>
                                                <td>
                                                    <span className={`badge ${u.is_active ? 'badge-success' : 'badge-neutral'}`}>
                                                        {u.is_active ? "Active" : "Inactive"}
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                        {units.length === 0 && (
                                            <tr>
                                                <td colSpan="3" style={{ textAlign: "center", color: "var(--text-muted)", padding: "20px" }}>No units configured yet.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {activeTab === "compliance" && isOwner && complianceReport && (
                        <div className="card">
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px", flexWrap: "wrap", gap: 16 }}>
                                <h3 style={{ margin: 0, color: "var(--text-main)" }}>Compliance Overview</h3>
                                <select className="cc-input" style={{ width: "auto" }} value={complianceDays} onChange={e => setComplianceDays(parseInt(e.target.value))}>
                                    <option value={7}>Last 7 Days</option>
                                    <option value={30}>Last 30 Days</option>
                                    <option value={90}>Last 90 Days</option>
                                </select>
                            </div>

                            <div className="cc-stat-grid">
                                <div className="cc-stat-card">
                                    <div className="cc-stat-val" style={{ color: complianceReport.compliance_pct >= 95 ? "var(--success-500, #10b981)" : "var(--danger-500, #ef4444)" }}>
                                        {complianceReport.compliance_pct.toFixed(1)}%
                                    </div>
                                    <div className="cc-stat-lbl">Overall Compliance</div>
                                </div>
                                <div className="cc-stat-card">
                                    <div className="cc-stat-val">{complianceReport.total_readings}</div>
                                    <div className="cc-stat-lbl">Total Readings</div>
                                </div>
                                <div className="cc-stat-card">
                                    <div className="cc-stat-val">{complianceReport.excursion_count}</div>
                                    <div className="cc-stat-lbl">Total Excursions</div>
                                </div>
                            </div>

                            <h3 style={{ color: "var(--text-main)", marginTop: 32 }}>Daily Compliance Trend</h3>
                            <div style={{ height: "300px", marginBottom: "32px", background: "var(--bg-surface)", padding: 16, borderRadius: 8, border: "1px solid var(--border-color)" }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={complianceReport.daily_trend}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
                                        <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} />
                                        <YAxis domain={[0, 100]} stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} />
                                        <Tooltip 
                                            contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-color)', color: 'var(--text-main)', borderRadius: 8 }}
                                        />
                                        <Line type="monotone" dataKey="compliance_pct" stroke="var(--primary-500)" strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} name="Compliance %" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>

                            <h3 style={{ color: "var(--text-main)" }}>Per-Unit Breakdown</h3>
                            <div style={{ overflowX: "auto" }}>
                                <table className="table">
                                    <thead>
                                        <tr>
                                            <th>Unit</th>
                                            <th>Compliance</th>
                                            <th>Excursions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {complianceReport.units.map(u => (
                                            <tr key={u.unit_id}>
                                                <td style={{ fontWeight: 500 }}>{u.unit_label}</td>
                                                <td style={{ color: u.compliance_pct >= 95 ? "var(--success-500, #10b981)" : "var(--danger-500, #ef4444)", fontWeight: "600" }}>
                                                    {u.compliance_pct.toFixed(1)}%
                                                </td>
                                                <td>{u.excursion_count} / {u.total_readings}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {activeTab === "alerts" && isOwner && (
                        <div className="card">
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: 16 }}>
                                <h3 style={{ margin: 0, color: "var(--text-main)" }}>Compromised Stock Check</h3>
                                <select className="cc-input" style={{ width: "auto" }} value={selectedCompUnit} onChange={e => setSelectedCompUnit(e.target.value)}>
                                    {units.map(u => <option key={u.id} value={u.id}>{u.unit_label}</option>)}
                                </select>
                            </div>
                            <p style={{ color: "var(--text-muted)", marginBottom: "24px", display: "flex", alignItems: "flex-start", gap: 8 }}>
                                <Info size={20} style={{ flexShrink: 0, marginTop: 2, color: "var(--primary-500)" }} />
                                Review medicines stored in this unit that require cold-chain compliance. If an excursion occurred, these batches may need redistribution or disposal.
                            </p>
                            
                            {compromisedBatches.length === 0 ? (
                                <div style={{ textAlign: "center", padding: "40px 20px", background: "var(--bg-surface)", borderRadius: 8, border: "1px dashed var(--border-color)" }}>
                                    <CheckCircle size={32} style={{ color: "var(--success-500)", marginBottom: 12 }} />
                                    <p style={{ margin: 0, color: "var(--text-muted)" }}>No cold-chain batches found for this unit.</p>
                                </div>
                            ) : (
                                <div style={{ overflowX: "auto" }}>
                                    <table className="table">
                                        <thead>
                                            <tr style={{ backgroundColor: "var(--bg-hover, #f8fafc)" }}>
                                                <th>Medicine</th>
                                                <th>Batch No</th>
                                                <th>Expiry Date</th>
                                                <th>Action</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {compromisedBatches.map(b => (
                                                <tr key={b.batch_id}>
                                                    <td style={{ fontWeight: 500 }}>{b.medicine_name}</td>
                                                    <td>{b.batch_no || "N/A"}</td>
                                                    <td>{b.expiry_date || "N/A"}</td>
                                                    <td>
                                                        <button className="btn btn-danger btn-sm" style={{ padding: "4px 8px", fontSize: "12px" }}>Mark for Network</button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    )}
                </motion.div>
            </AnimatePresence>
        </motion.div>
    );
}
