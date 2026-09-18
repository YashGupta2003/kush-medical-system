import { useState } from "react";
import { apiFetch } from "../api/client";

export function VoiceConfirmationCard({ parsedResult, onConfirm, onCancel }) {
  const { parsed, resolved_medicine } = parsedResult;
  const isUnclear = parsed.intent === "unclear" || !resolved_medicine;

  const [intent, setIntent] = useState(parsed.intent === "unclear" ? "sell" : parsed.intent);
  const [quantity, setQuantity] = useState(parsed.quantity || 1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleConfirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        intent,
        medicine_id: resolved_medicine?.id,
        quantity: parseInt(quantity, 10),
      };
      
      const res = await apiFetch("/v1/voice/confirm", {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
          "Content-Type": "application/json",
        }
      });
      onConfirm(res);
    } catch (err) {
      setError(err.message || "Confirmation failed");
      setSubmitting(false);
    }
  };

  return (
    <div className="voice-confirm-card">
      <div className="vcc-header">
        <h4>Voice Command Parsed</h4>
        <div className="vcc-confidence">Confidence: {Math.round(parsed.confidence * 100)}%</div>
      </div>
      
      <div className="vcc-transcript">
        "{parsed.raw_transcript}"
      </div>

      {!isUnclear ? (
        <div className="vcc-summary">
          <span className="vcc-bold">Samjha:</span> {resolved_medicine.name} &times; {parsed.quantity} {parsed.unit} &mdash; <span className="vcc-intent">{parsed.intent}</span>
        </div>
      ) : (
        <div className="vcc-edit-form">
          <div className="vcc-warning">
            {parsedResult.message || "Command was unclear or medicine not found. Please edit below."}
          </div>
          {resolved_medicine && (
            <div className="vcc-summary">
              Medicine: <b>{resolved_medicine.name}</b>
            </div>
          )}
          
          <div className="vcc-field-row">
            <label>Action:</label>
            <select value={intent} onChange={(e) => setIntent(e.target.value)}>
              <option value="sell">Sell</option>
              <option value="restock">Restock</option>
              <option value="check_stock">Check Stock</option>
            </select>
          </div>
          
          <div className="vcc-field-row">
            <label>Quantity:</label>
            <input 
              type="number" 
              value={quantity} 
              onChange={(e) => setQuantity(e.target.value)}
              min="1"
            />
          </div>
        </div>
      )}

      {error && <div className="vcc-error">{error}</div>}

      <div className="vcc-actions">
        <button className="btn btn-outline" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button 
          className="btn btn-primary" 
          onClick={handleConfirm} 
          disabled={submitting || !resolved_medicine}
        >
          {submitting ? "Confirming..." : "Confirm"}
        </button>
      </div>

      <style>{`
        .voice-confirm-card {
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 16px;
          background: #fff;
          box-shadow: 0 4px 12px rgba(0,0,0,0.05);
          animation: slideDown 0.3s ease;
        }
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .vcc-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }
        .vcc-header h4 {
          margin: 0;
          font-size: 15px;
          font-weight: 600;
        }
        .vcc-confidence {
          font-size: 12px;
          color: var(--text-muted);
          background: var(--bg-surface);
          padding: 2px 8px;
          border-radius: 12px;
        }
        .vcc-transcript {
          font-size: 13px;
          color: var(--text-muted);
          font-style: italic;
          margin-bottom: 12px;
          padding-bottom: 12px;
          border-bottom: 1px solid var(--border);
        }
        .vcc-summary {
          font-size: 14.5px;
          margin-bottom: 16px;
        }
        .vcc-bold {
          font-weight: 600;
        }
        .vcc-intent {
          text-transform: uppercase;
          font-weight: 700;
          font-size: 12px;
          background: var(--primary-100);
          color: var(--primary-700);
          padding: 2px 6px;
          border-radius: 4px;
        }
        .vcc-warning {
          color: var(--danger);
          font-size: 13px;
          margin-bottom: 12px;
        }
        .vcc-field-row {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 12px;
        }
        .vcc-field-row label {
          font-size: 13px;
          font-weight: 600;
          width: 70px;
        }
        .vcc-field-row select, .vcc-field-row input {
          flex: 1;
          padding: 6px 10px;
          border: 1px solid var(--border);
          border-radius: 6px;
        }
        .vcc-error {
          color: var(--danger);
          font-size: 13px;
          margin-bottom: 12px;
        }
        .vcc-actions {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          margin-top: 16px;
        }
      `}</style>
    </div>
  );
}
