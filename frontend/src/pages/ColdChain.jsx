import React, { useState, useEffect } from "react";
import { api } from "../api/client";
import { AreaChart, Area, BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";

export default function ColdChain({ isOwner }) {
    const [activeTab, setActiveTab] = useState("log");
    
    // Log Tab
    const [units, setUnits] = useState([]);
    const [selectedUnit, setSelectedUnit] = useState("");
    const [temp, setTemp] = useState("");
    const [note, setNote] = useState("");
    const [recentReadings, setRecentReadings] = useState([]);
    const [logStatus, setLogStatus] = useState(null);

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
        <div className="page-container">
            <style>{`
                .cc-header { margin-bottom: 24px; }
                .cc-header h1 { margin: 0 0 8px 0; font-size: 24px; color: #1e293b; }
                .cc-header p { margin: 0; color: #64748b; font-size: 14px; }
                .cc-tabs { display: flex; gap: 16px; margin-bottom: 24px; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px; }
                .cc-tab { background: none; border: none; padding: 8px 16px; font-weight: 500; color: #64748b; cursor: pointer; border-radius: 6px; }
                .cc-tab.active { background: #eff6ff; color: #2563eb; }
                .cc-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px; margin-bottom: 24px; }
                .cc-form-group { margin-bottom: 16px; }
                .cc-form-group label { display: block; margin-bottom: 8px; font-weight: 500; font-size: 14px; }
                .cc-input { width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 14px; }
                .cc-btn { background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 500; }
                .cc-btn:hover { background: #1d4ed8; }
                .cc-reading-row { display: flex; justify-content: space-between; align-items: center; padding: 12px; border-bottom: 1px solid #e2e8f0; }
                .cc-reading-row:last-child { border-bottom: none; }
                .cc-badge { padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
                .cc-badge.excursion { background: #fef2f2; color: #ef4444; }
                .cc-badge.normal { background: #f0fdf4; color: #16a34a; }
                .cc-stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
                .cc-stat-card { background: #f8fafc; padding: 16px; border-radius: 8px; text-align: center; border: 1px solid #e2e8f0; }
                .cc-stat-val { font-size: 28px; font-weight: bold; color: #0f172a; }
                .cc-stat-lbl { font-size: 13px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
            `}</style>

            <div className="cc-header">
                <h1>🧊 Cold-Chain Compliance</h1>
                <p>Monitor fridge temperatures, detect excursions, and maintain regulatory compliance.</p>
            </div>

            <div className="cc-tabs">
                <button className={`cc-tab ${activeTab === "log" ? "active" : ""}`} onClick={() => setActiveTab("log")}>Log Reading</button>
                {isOwner && (
                    <>
                        <button className={`cc-tab ${activeTab === "units" ? "active" : ""}`} onClick={() => setActiveTab("units")}>Manage Units</button>
                        <button className={`cc-tab ${activeTab === "compliance" ? "active" : ""}`} onClick={() => setActiveTab("compliance")}>Compliance Report</button>
                        <button className={`cc-tab ${activeTab === "alerts" ? "active" : ""}`} onClick={() => setActiveTab("alerts")}>Excursion Alerts</button>
                    </>
                )}
            </div>

            {activeTab === "log" && (
                <div className="cc-card">
                    <h3>Record Temperature</h3>
                    <form onSubmit={handleLogReading} style={{ maxWidth: "400px", marginBottom: "32px" }}>
                        <div className="cc-form-group">
                            <label>Select Unit</label>
                            <select className="cc-input" value={selectedUnit} onChange={(e) => setSelectedUnit(e.target.value)} required>
                                {units.map(u => <option key={u.id} value={u.id}>{u.unit_label}</option>)}
                            </select>
                        </div>
                        <div className="cc-form-group">
                            <label>Temperature (°C)</label>
                            <input type="number" step="0.1" className="cc-input" value={temp} onChange={(e) => setTemp(e.target.value)} required />
                        </div>
                        <div className="cc-form-group">
                            <label>Note (Optional)</label>
                            <input type="text" className="cc-input" value={note} onChange={(e) => setNote(e.target.value)} />
                        </div>
                        <button type="submit" className="cc-btn">Log Reading</button>
                        {logStatus && (
                            <div style={{ marginTop: "12px", color: logStatus.type === "error" ? "red" : "green" }}>
                                {logStatus.msg}
                            </div>
                        )}
                    </form>

                    <h3>Recent Readings (24h)</h3>
                    {recentReadings.length === 0 ? <p>No readings in the last 24 hours.</p> : (
                        <div style={{ border: "1px solid #e2e8f0", borderRadius: "8px" }}>
                            {recentReadings.map(r => (
                                <div key={r.id} className="cc-reading-row">
                                    <div>
                                        <div style={{ fontWeight: 500 }}>{r.recorded_temp_c}°C</div>
                                        <div style={{ fontSize: "12px", color: "#64748b" }}>{new Date(r.recorded_at).toLocaleString()} by {r.recorded_by_username || "System"}</div>
                                    </div>
                                    <div>
                                        {r.is_excursion ? <span className="cc-badge excursion">Excursion</span> : <span className="cc-badge normal">Compliant</span>}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {activeTab === "units" && isOwner && (
                <div className="cc-card">
                    <h3>Create New Unit</h3>
                    <form onSubmit={handleCreateUnit} style={{ maxWidth: "400px", marginBottom: "32px" }}>
                        <div className="cc-form-group">
                            <label>Unit Label</label>
                            <input type="text" className="cc-input" value={newUnit.unit_label} onChange={e => setNewUnit({...newUnit, unit_label: e.target.value})} required />
                        </div>
                        <div style={{ display: "flex", gap: "16px" }}>
                            <div className="cc-form-group">
                                <label>Min Temp (°C)</label>
                                <input type="number" step="0.1" className="cc-input" value={newUnit.min_temp_c} onChange={e => setNewUnit({...newUnit, min_temp_c: e.target.value})} required />
                            </div>
                            <div className="cc-form-group">
                                <label>Max Temp (°C)</label>
                                <input type="number" step="0.1" className="cc-input" value={newUnit.max_temp_c} onChange={e => setNewUnit({...newUnit, max_temp_c: e.target.value})} required />
                            </div>
                        </div>
                        <button type="submit" className="cc-btn">Create Unit</button>
                    </form>

                    <h3>Configured Units</h3>
                    <table style={{ width: "100%", textAlign: "left", borderCollapse: "collapse" }}>
                        <thead>
                            <tr style={{ borderBottom: "2px solid #e2e8f0" }}>
                                <th style={{ padding: "12px" }}>Label</th>
                                <th style={{ padding: "12px" }}>Safe Range</th>
                                <th style={{ padding: "12px" }}>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {units.map(u => (
                                <tr key={u.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                                    <td style={{ padding: "12px" }}>{u.unit_label}</td>
                                    <td style={{ padding: "12px" }}>{u.min_temp_c}°C – {u.max_temp_c}°C</td>
                                    <td style={{ padding: "12px" }}>{u.is_active ? "Active" : "Inactive"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {activeTab === "compliance" && isOwner && complianceReport && (
                <div className="cc-card">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
                        <h3>Compliance Overview</h3>
                        <select className="cc-input" style={{ width: "auto" }} value={complianceDays} onChange={e => setComplianceDays(parseInt(e.target.value))}>
                            <option value={7}>Last 7 Days</option>
                            <option value={30}>Last 30 Days</option>
                            <option value={90}>Last 90 Days</option>
                        </select>
                    </div>

                    <div className="cc-stat-grid">
                        <div className="cc-stat-card">
                            <div className="cc-stat-val" style={{ color: complianceReport.compliance_pct >= 95 ? "#16a34a" : "#ef4444" }}>
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

                    <h3>Daily Compliance Trend</h3>
                    <div style={{ height: "300px", marginBottom: "32px" }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={complianceReport.daily_trend}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="date" />
                                <YAxis domain={[0, 100]} />
                                <Tooltip />
                                <Line type="monotone" dataKey="compliance_pct" stroke="#2563eb" strokeWidth={2} name="Compliance %" />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>

                    <h3>Per-Unit Breakdown</h3>
                    <table style={{ width: "100%", textAlign: "left", borderCollapse: "collapse" }}>
                        <thead>
                            <tr style={{ borderBottom: "2px solid #e2e8f0" }}>
                                <th style={{ padding: "12px" }}>Unit</th>
                                <th style={{ padding: "12px" }}>Compliance</th>
                                <th style={{ padding: "12px" }}>Excursions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {complianceReport.units.map(u => (
                                <tr key={u.unit_id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                                    <td style={{ padding: "12px", fontWeight: 500 }}>{u.unit_label}</td>
                                    <td style={{ padding: "12px", color: u.compliance_pct >= 95 ? "#16a34a" : "#ef4444", fontWeight: "bold" }}>
                                        {u.compliance_pct.toFixed(1)}%
                                    </td>
                                    <td style={{ padding: "12px" }}>{u.excursion_count} / {u.total_readings}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {activeTab === "alerts" && isOwner && (
                <div className="cc-card">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
                        <h3>Compromised Stock Check</h3>
                        <select className="cc-input" style={{ width: "auto" }} value={selectedCompUnit} onChange={e => setSelectedCompUnit(e.target.value)}>
                            {units.map(u => <option key={u.id} value={u.id}>{u.unit_label}</option>)}
                        </select>
                    </div>
                    <p style={{ color: "#64748b", marginBottom: "24px" }}>Review medicines stored in this unit that require cold-chain compliance. If an excursion occurred, these batches may need redistribution or disposal.</p>
                    
                    {compromisedBatches.length === 0 ? <p>No cold-chain batches found for this unit.</p> : (
                        <table style={{ width: "100%", textAlign: "left", borderCollapse: "collapse" }}>
                            <thead>
                                <tr style={{ borderBottom: "2px solid #e2e8f0", backgroundColor: "#f8fafc" }}>
                                    <th style={{ padding: "12px" }}>Medicine</th>
                                    <th style={{ padding: "12px" }}>Batch No</th>
                                    <th style={{ padding: "12px" }}>Expiry Date</th>
                                    <th style={{ padding: "12px" }}>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {compromisedBatches.map(b => (
                                    <tr key={b.batch_id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                                        <td style={{ padding: "12px", fontWeight: 500 }}>{b.medicine_name}</td>
                                        <td style={{ padding: "12px" }}>{b.batch_no || "N/A"}</td>
                                        <td style={{ padding: "12px" }}>{b.expiry_date || "N/A"}</td>
                                        <td style={{ padding: "12px" }}>
                                            <button className="cc-btn" style={{ padding: "4px 8px", fontSize: "12px", backgroundColor: "#ef4444" }}>Mark for Network</button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
        </div>
    );
}
