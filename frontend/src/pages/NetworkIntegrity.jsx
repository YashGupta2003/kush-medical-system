import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ShieldExclamationIcon, ShieldCheckIcon, AdjustmentsHorizontalIcon } from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';

export default function NetworkIntegrity() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("open");
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    loadAlerts();
  }, [statusFilter]);

  const loadAlerts = async () => {
    setLoading(true);
    try {
      const data = await api.getNetworkIntegrityAlerts(statusFilter);
      setAlerts(data);
    } catch (err) {
      toast.error(err.message || 'Failed to load network alerts');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (alertId, newStatus) => {
    try {
      await api.updateAlertStatus(alertId, newStatus);
      toast.success(`Alert marked as ${newStatus}`);
      loadAlerts();
    } catch (err) {
      toast.error(err.message || `Failed to mark alert as ${newStatus}`);
    }
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await api.triggerCollisionScan();
      toast.success("Cross-tenant scan triggered. Refresh in a moment.");
    } catch (err) {
      toast.error(err.message || 'Failed to trigger scan');
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 flex items-center">
            <ShieldExclamationIcon className="h-6 w-6 text-red-500 mr-2" />
            Network Integrity Alerts
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Detects counterfeit / grey-market batches crossing multi-tenant boundaries.
          </p>
        </div>
        <div className="flex space-x-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="block w-40 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          >
            <option value="open">Open</option>
            <option value="reviewed">Reviewed</option>
            <option value="dismissed">Dismissed</option>
          </select>
          <button
            onClick={handleScan}
            disabled={scanning}
            className="inline-flex items-center rounded-md border border-transparent bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            <AdjustmentsHorizontalIcon className="-ml-1 mr-2 h-5 w-5" />
            {scanning ? "Scanning..." : "Force Scan Now"}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center text-sm text-gray-500 py-10">Loading alerts...</div>
      ) : alerts.length === 0 ? (
        <div className="text-center bg-white rounded-lg shadow px-4 py-10">
          <ShieldCheckIcon className="mx-auto h-12 w-12 text-green-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No {statusFilter} alerts</h3>
          <p className="mt-1 text-sm text-gray-500">Your supply chain appears clean across the network.</p>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul role="list" className="divide-y divide-gray-200">
            {alerts.map((alert) => (
              <li key={alert.id} className="px-4 py-4 sm:px-6">
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <p className="text-sm font-medium text-indigo-600 truncate">
                      {alert.medicine_name}
                    </p>
                    <p className="flex items-center text-sm text-gray-500 mt-1">
                      Batch: <span className="font-mono font-medium ml-1 text-gray-900">{alert.normalized_batch_no}</span>
                    </p>
                  </div>
                  <div className="ml-2 flex-shrink-0 flex space-x-2">
                    {alert.status === 'open' && (
                      <>
                        <button
                          onClick={() => handleUpdateStatus(alert.id, 'reviewed')}
                          className="inline-flex items-center px-2.5 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
                        >
                          Mark Reviewed
                        </button>
                        <button
                          onClick={() => handleUpdateStatus(alert.id, 'dismissed')}
                          className="inline-flex items-center px-2.5 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-red-700 bg-red-50 hover:bg-red-100"
                        >
                          Dismiss
                        </button>
                      </>
                    )}
                    <span
                      className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        alert.severity === 'high' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                      }`}
                    >
                      {alert.severity.toUpperCase()}
                    </span>
                  </div>
                </div>
                <div className="mt-2 sm:flex sm:justify-between">
                  <div className="sm:flex">
                    <p className="flex items-center text-sm text-gray-500">
                      Detected across <strong className="mx-1">{alert.other_pharmacies_involved}</strong> other pharmacies
                    </p>
                  </div>
                  <div className="mt-2 flex items-center text-sm text-gray-500 sm:mt-0">
                    <p>
                      Seen <span className="font-medium text-gray-900">{alert.occurrence_count}</span> times total
                    </p>
                  </div>
                </div>
                <div className="mt-2 text-xs text-gray-500 bg-gray-50 p-2 rounded">
                  Distributors involved: {alert.distributor_names.join(', ')}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
