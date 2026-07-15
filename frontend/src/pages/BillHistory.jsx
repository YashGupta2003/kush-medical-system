import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";

export default function BillHistory() {
  const [bills, setBills] = useState([]);

  useEffect(() => {
    api.listBills().then(setBills);
  }, []);

  return (
    <div className="card">
      <h2>Bill history</h2>
      <p style={{ color: "#666", fontSize: 13 }}>
        Every bill ever uploaded, with the distributor it came from and the month it arrived.
      </p>
      <table>
        <thead>
          <tr><th>Date</th><th>Distributor</th><th>Invoice no.</th><th>Total</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {bills.map((b) => (
            <tr key={b.id}>
              <td>{b.year}-{String(b.month).padStart(2, "0")}</td>
              <td>{b.distributor_name || "—"}</td>
              <td>{b.invoice_no || "—"}</td>
              <td>{b.total_amount}</td>
              <td><span className={`badge ${b.status === "confirmed" ? "auto" : "manual"}`}>{b.status}</span></td>
              <td>{b.status === "pending_review" && <Link to={`/review/${b.id}`}>Review</Link>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
