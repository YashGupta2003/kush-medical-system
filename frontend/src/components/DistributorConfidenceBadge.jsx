import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { HelpCircle, CheckCircle, AlertTriangle, Activity } from 'lucide-react';
import '../styles/DistributorConfidenceBadge.css';

export default function DistributorConfidenceBadge({ distributorId }) {
  const [confidenceData, setConfidenceData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!distributorId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api.getDistributorConfidence(distributorId)
      .then((res) => {
        if (res.ok) return res.json();
        return null;
      })
      .then((data) => {
        setConfidenceData(data);
      })
      .catch((err) => console.error("Error fetching confidence:", err))
      .finally(() => setLoading(false));
  }, [distributorId]);

  if (loading || !confidenceData) return null;

  const { status, overall_confidence_pct, sample_count, low_confidence_fields } = confidenceData;

  if (status === 'not_learned') return null;

  const getIcon = () => {
    if (status === 'confident') return <CheckCircle size={16} className="status-icon success" />;
    if (status === 'needs_attention') return <AlertTriangle size={16} className="status-icon warning" />;
    return <Activity size={16} className="status-icon info" />;
  };

  const getLabel = () => {
    if (status === 'confident') return `${overall_confidence_pct}% Layout Confidence`;
    if (status === 'needs_attention') return `Low Confidence (${overall_confidence_pct}%)`;
    return `Learning Layout (bills: ${sample_count})`;
  };

  return (
    <div className={`distributor-confidence-badge status-${status}`} title={`Based on ${sample_count} confirmed bills`}>
      {getIcon()}
      <span className="badge-label">{getLabel()}</span>
      {low_confidence_fields && low_confidence_fields.length > 0 && (
        <span className="low-conf-fields" title={`Fields that often require correction: ${low_confidence_fields.join(', ')}`}>
          <HelpCircle size={14} />
        </span>
      )}
    </div>
  );
}
