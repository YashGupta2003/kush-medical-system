import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { api } from '../api/client.js';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, TrendingUp, AlertCircle, RefreshCw, BarChart2 } from 'lucide-react';

export default function Surveillance() {
    const [activeTab, setActiveTab] = useState('overview');
    const [conditions, setConditions] = useState([]);
    const [spikes, setSpikes] = useState([]);
    const [selectedCondition, setSelectedCondition] = useState('');
    const [trendData, setTrendData] = useState([]);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const [conds, spks] = await Promise.all([
                api.getSurveillanceConditions(),
                api.getSurveillanceSpikes()
            ]);
            setConditions(conds);
            setSpikes(spks);
            if (conds.length > 0 && !selectedCondition) {
                setSelectedCondition(conds[0].condition_name);
                loadTrend(conds[0].condition_name);
            }
        } catch (error) {
            console.error("Failed to load surveillance data", error);
        }
        setLoading(false);
    };

    const loadTrend = async (cond) => {
        try {
            const data = await api.getSurveillanceTrend(cond, 30);
            setTrendData(data);
        } catch (error) {
            console.error("Failed to load trend data", error);
        }
    };

    const handleConditionSelect = (cond) => {
        setSelectedCondition(cond);
        loadTrend(cond);
        setActiveTab('trend');
    };

    const handleManualScan = async () => {
        await api.triggerSurveillanceScan();
        alert("Scan started in the background.");
    };

    if (loading) return (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            <RefreshCw className="animate-spin" style={{ marginRight: '8px' }} /> Loading Surveillance Data...
        </div>
    );

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
                .header-section h2 { margin: 0; color: var(--text-main); display: flex; align-items: center; gap: 8px; }
                
                .tabs-nav { display: flex; gap: 8px; margin-bottom: 24px; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; overflow-x: auto; }
                .tab-btn { background: none; border: none; font-size: 14px; font-weight: 500; padding: 8px 16px; cursor: pointer; color: var(--text-muted); display: flex; align-items: center; gap: 6px; border-radius: 6px; transition: all 0.2s; white-space: nowrap; }
                .tab-btn:hover { background: var(--bg-hover, rgba(0,0,0,0.05)); }
                .tab-btn.active { color: var(--primary-500); background: var(--primary-50, rgba(37, 99, 235, 0.1)); }
                
                .conditions-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
                .condition-card { background: var(--bg-surface); padding: 20px; border-radius: 12px; border: 1px solid var(--border-color); cursor: pointer; transition: all 0.2s; }
                .condition-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-color: var(--primary-500); }
                .condition-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
                .condition-card-title { font-weight: 600; font-size: 16px; color: var(--text-main); line-height: 1.3; }
                
                .stat-row { display: flex; justify-content: space-between; font-size: 14px; color: var(--text-muted); margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 4px; }
                .stat-row:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
                
                .chart-container { background: var(--bg-surface); padding: 24px; border-radius: 12px; border: 1px solid var(--border-color); height: 400px; margin-top: 16px; }
                
                .spikes-list { display: flex; flex-direction: column; gap: 16px; }
                .spike-item { background: var(--danger-50, #fef2f2); border-left: 4px solid var(--danger-500, #ef4444); padding: 16px 20px; border-radius: 0 8px 8px 0; display: flex; flex-direction: column; gap: 8px; }
                .spike-title { font-weight: 600; color: var(--danger-700, #b91c1c); display: flex; align-items: center; gap: 6px; font-size: 16px; }
                .spike-desc { color: var(--text-main); font-size: 14px; }
                
                select.custom-select { padding: 10px 16px; font-size: 14px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--bg-surface); color: var(--text-main); outline: none; min-width: 250px; cursor: pointer; }
                select.custom-select:focus { border-color: var(--primary-500); box-shadow: 0 0 0 2px var(--primary-50, rgba(37, 99, 235, 0.2)); }
            `}</style>

            <div className="header-section">
                <h2><Activity className="icon" size={28} style={{ color: "var(--primary-500)" }} /> Regional Health Pulse</h2>
                <button className="btn btn-primary" onClick={handleManualScan} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <RefreshCw size={16} /> Run Scan Now
                </button>
            </div>

            <div className="tabs-nav">
                <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
                    <BarChart2 size={16} /> Conditions Overview
                </button>
                <button className={`tab-btn ${activeTab === 'trend' ? 'active' : ''}`} onClick={() => setActiveTab('trend')}>
                    <TrendingUp size={16} /> Trend Analysis
                </button>
                <button className={`tab-btn ${activeTab === 'alerts' ? 'active' : ''}`} onClick={() => setActiveTab('alerts')}>
                    <AlertCircle size={16} /> Spike Alerts ({spikes.length})
                </button>
            </div>

            <AnimatePresence mode="wait">
                <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    transition={{ duration: 0.15 }}
                >
                    {activeTab === 'overview' && (
                        <div className="conditions-grid">
                            {conditions.map(cond => (
                                <div key={cond.condition_name} className="condition-card" onClick={() => handleConditionSelect(cond.condition_name)}>
                                    <div className="condition-card-header">
                                        <div className="condition-card-title">{cond.condition_name}</div>
                                        {cond.has_spike ? (
                                            <span className="badge badge-danger" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                                <TrendingUp size={12}/> SPIKE
                                            </span>
                                        ) : (
                                            <span className="badge badge-success">Normal</span>
                                        )}
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                        <div className="stat-row">
                                            <span>7-Day Total:</span>
                                            <span style={{ fontWeight: 500, color: 'var(--text-main)' }}>{cond.total_units_7d} units</span>
                                        </div>
                                        <div className="stat-row">
                                            <span>Avg Daily:</span>
                                            <span style={{ fontWeight: 500, color: 'var(--text-main)' }}>{cond.avg_daily.toFixed(1)} units</span>
                                        </div>
                                        {cond.latest_z_score !== null && (
                                            <div className="stat-row">
                                                <span>Latest Z-Score:</span>
                                                <span style={{ fontWeight: 500, color: cond.latest_z_score > 2 ? 'var(--danger-500)' : 'var(--text-main)' }}>
                                                    {cond.latest_z_score.toFixed(2)}
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {activeTab === 'trend' && (
                        <div>
                            <select 
                                value={selectedCondition} 
                                onChange={(e) => handleConditionSelect(e.target.value)}
                                className="custom-select"
                            >
                                {conditions.map(c => (
                                    <option key={c.condition_name} value={c.condition_name}>{c.condition_name}</option>
                                ))}
                            </select>
                            
                            <div className="chart-container">
                                <h3 style={{ margin: '0 0 20px 0', color: 'var(--text-main)', fontSize: '16px' }}>{selectedCondition} - 30 Day Trend</h3>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
                                        <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} dy={10} />
                                        <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} />
                                        <Tooltip 
                                            contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-color)', borderRadius: '8px', color: 'var(--text-main)' }}
                                            itemStyle={{ color: 'var(--primary-500)' }}
                                        />
                                        <Line type="monotone" dataKey="otc_units" name="Units" stroke="var(--primary-500)" strokeWidth={3} dot={{ r: 4, fill: 'var(--bg-surface)', strokeWidth: 2 }} activeDot={{ r: 6, fill: 'var(--primary-500)' }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}

                    {activeTab === 'alerts' && (
                        <div className="spikes-list">
                            {spikes.length === 0 ? (
                                <div style={{ textAlign: "center", padding: "40px 20px", background: "var(--bg-surface)", borderRadius: 8, border: "1px dashed var(--border-color)" }}>
                                    <Activity size={32} style={{ color: "var(--success-500)", marginBottom: 12, opacity: 0.5 }} />
                                    <p style={{ margin: 0, color: "var(--text-muted)" }}>No active spikes detected in the last 14 days.</p>
                                </div>
                            ) : (
                                spikes.map((spike, idx) => (
                                    <div key={idx} className="spike-item">
                                        <div className="spike-title"><AlertCircle size={18} /> Spike in {spike.condition_name}</div>
                                        <div className="spike-desc">
                                            On <strong>{spike.spike_date}</strong>, sales hit <strong>{spike.count} units</strong> 
                                            {" "}(Average is normally {spike.avg_count.toFixed(1)} units).
                                        </div>
                                        <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                                            <TrendingUp size={14} /> Z-Score: <span style={{ fontWeight: 600 }}>{spike.z_score.toFixed(2)}</span>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </motion.div>
            </AnimatePresence>
        </motion.div>
    );
}
