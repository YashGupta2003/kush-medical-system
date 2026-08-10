import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { api } from '../api/client.js';

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

    if (loading) return <div>Loading Surveillance Data...</div>;

    return (
        <div className="surveillance-container">
            <style>{`
                .surveillance-container { padding: 20px; max-width: 1200px; margin: 0 auto; }
                .header-section { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
                .scan-btn { background: #3b82f6; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
                .scan-btn:hover { background: #2563eb; }
                .tabs-nav { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid #e5e7eb; padding-bottom: 10px; }
                .tab-btn { background: none; border: none; font-size: 16px; padding: 8px 16px; cursor: pointer; color: #6b7280; }
                .tab-btn.active { color: #1f2937; border-bottom: 2px solid #3b82f6; font-weight: bold; }
                .conditions-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 16px; }
                .card { background: white; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e5e7eb; cursor: pointer; }
                .card:hover { box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
                .card-title { font-weight: bold; font-size: 1.1em; color: #111827; }
                .badge { padding: 4px 8px; border-radius: 9999px; font-size: 0.8em; font-weight: bold; }
                .badge.spike { background: #fee2e2; color: #991b1b; }
                .badge.normal { background: #d1fae5; color: #065f46; }
                .stat-row { display: flex; justify-content: space-between; font-size: 0.9em; color: #4b5563; margin-top: 4px; }
                .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e5e7eb; height: 400px; margin-top: 20px; }
                .spikes-list { display: flex; flex-direction: column; gap: 12px; }
                .spike-item { background: #fff5f5; border-left: 4px solid #f56565; padding: 16px; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
                .spike-title { font-weight: bold; color: #c53030; margin-bottom: 8px; }
            `}</style>

            <div className="header-section">
                <h2>Regional Health Pulse (Surveillance)</h2>
                <button className="scan-btn" onClick={handleManualScan}>Run Scan Now</button>
            </div>

            <div className="tabs-nav">
                <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
                    Conditions Overview
                </button>
                <button className={`tab-btn ${activeTab === 'trend' ? 'active' : ''}`} onClick={() => setActiveTab('trend')}>
                    Trend Analysis
                </button>
                <button className={`tab-btn ${activeTab === 'alerts' ? 'active' : ''}`} onClick={() => setActiveTab('alerts')}>
                    Spike Alerts ({spikes.length})
                </button>
            </div>

            {activeTab === 'overview' && (
                <div className="conditions-grid">
                    {conditions.map(cond => (
                        <div key={cond.condition_name} className="card" onClick={() => handleConditionSelect(cond.condition_name)}>
                            <div className="card-header">
                                <div className="card-title">{cond.condition_name}</div>
                                {cond.has_spike ? (
                                    <span className="badge spike">SPIKE</span>
                                ) : (
                                    <span className="badge normal">Normal</span>
                                )}
                            </div>
                            <div className="stat-row">
                                <span>7-Day Total:</span>
                                <span>{cond.total_units_7d} units</span>
                            </div>
                            <div className="stat-row">
                                <span>Avg Daily:</span>
                                <span>{cond.avg_daily.toFixed(1)} units</span>
                            </div>
                            {cond.latest_z_score !== null && (
                                <div className="stat-row">
                                    <span>Latest Z-Score:</span>
                                    <span>{cond.latest_z_score.toFixed(2)}</span>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {activeTab === 'trend' && (
                <div>
                    <select 
                        value={selectedCondition} 
                        onChange={(e) => handleConditionSelect(e.target.value)}
                        style={{ padding: '8px', fontSize: '16px', borderRadius: '4px', border: '1px solid #ccc' }}
                    >
                        {conditions.map(c => (
                            <option key={c.condition_name} value={c.condition_name}>{c.condition_name}</option>
                        ))}
                    </select>
                    
                    <div className="chart-container">
                        <h3>{selectedCondition} - 30 Day Trend</h3>
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={trendData} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="date" />
                                <YAxis />
                                <Tooltip />
                                <Line type="monotone" dataKey="otc_units" stroke="#3182ce" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {activeTab === 'alerts' && (
                <div className="spikes-list">
                    {spikes.length === 0 ? (
                        <p>No active spikes detected in the last 14 days.</p>
                    ) : (
                        spikes.map((spike, idx) => (
                            <div key={idx} className="spike-item">
                                <div className="spike-title">Spike in {spike.condition_name}</div>
                                <div>
                                    On <strong>{spike.spike_date}</strong>, sales hit <strong>{spike.count} units</strong> 
                                    (Average is normally {spike.avg_count.toFixed(1)} units).
                                </div>
                                <div style={{ fontSize: '0.9em', color: '#718096', marginTop: '4px' }}>
                                    Z-Score: {spike.z_score.toFixed(2)}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
}
