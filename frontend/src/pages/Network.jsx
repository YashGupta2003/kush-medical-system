import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Network as NetworkIcon, Store, Mail, Clock, Package, HelpCircle, CheckCircle, XCircle } from "lucide-react";
import { api } from "../api/client.js";

const TYPE_META = {
  near_expiry: { label: "Near expiry", icon: <Clock size={16} />, badge: "unmatched" },
  excess_stock: { label: "Excess stock", icon: <Package size={16} />, badge: "auto" },
  shortage_request: { label: "Shortage request", icon: <HelpCircle size={16} />, badge: "manual" },
};

const STATUS_META = {
  open: { label: "Open", color: "var(--info)", icon: null },
  claimed: { label: "Claimed", color: "var(--warning)", icon: null },
  fulfilled: { label: "Fulfilled", color: "var(--success)", icon: <CheckCircle size={12} /> },
  withdrawn: { label: "Withdrawn", color: "var(--text-muted)", icon: <XCircle size={12} /> },
};

function NodesPanel({ isOwner, nodes, selfNode, onRefresh }) {
  const [shopName, setShopName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleAdd(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.addNetworkNode({ shop_name: shopName, contact_phone: contactPhone || null });
      setShopName(""); setContactPhone("");
      onRefresh();
    } finally { setSaving(false); }
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 8, color: "var(--text-main)" }}>
        <Store size={20} color="var(--primary-500)" /> Participating pharmacies
      </h3>
      <p style={{ color: "var(--text-muted)", fontSize: 12.5 }}>
        Each row here stands in for a separately-deployed shop in a real multi-pharmacy rollout —
        for this project, other participating shops are modeled as rows you can add below. See
        the module docstring in <code style={{ background: "var(--bg-surface)", padding: "2px 4px", borderRadius: 4, border: "1px solid var(--border)" }}>network_service.py</code> for the full honest scoping note.
      </p>
      <table className="table">
        <thead><tr><th>Shop</th><th>Contact</th><th></th></tr></thead>
        <tbody>
          {nodes.map((n) => (
            <tr key={n.id}>
              <td>{n.shop_name} {n.is_self && <span className="badge auto" style={{ marginLeft: 6 }}>this shop</span>}</td>
              <td style={{ color: "var(--text-muted)" }}>{n.contact_phone || "—"}</td>
              <td></td>
            </tr>
          ))}
        </tbody>
      </table>
      {isOwner && (
        <form onSubmit={handleAdd} style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <input placeholder="Nearby pharmacy name" value={shopName} onChange={(e) => setShopName(e.target.value)} required style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
          <input placeholder="Contact phone (optional)" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} style={{ width: 160, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
          <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Adding..." : "Add pharmacy"}</button>
        </form>
      )}
    </div>
  );
}

function PostListingForm({ onPosted }) {
  const [listingType, setListingType] = useState("excess_stock");
  const [medicineName, setMedicineName] = useState("");
  const [composition, setComposition] = useState("");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true); setError(null);
    try {
      await api.createNetworkListing({
        listing_type: listingType, medicine_name: medicineName,
        composition: composition || null, quantity: quantity ? Number(quantity) : null, note: note || null,
      });
      setMedicineName(""); setComposition(""); setQuantity(""); setNote("");
      onPosted();
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 8, color: "var(--text-main)" }}>
        <Mail size={20} color="var(--info)" /> Post a listing
      </h3>
      <form onSubmit={handleSubmit}>
        <div style={{ display: "flex", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
          <select value={listingType} onChange={(e) => setListingType(e.target.value)} style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }}>
            <option value="excess_stock">Excess stock (I have too much)</option>
            <option value="shortage_request">Shortage request (I need this)</option>
          </select>
          <input placeholder="Medicine name" value={medicineName} onChange={(e) => setMedicineName(e.target.value)} required style={{ flex: 1, minWidth: 160, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
          <input placeholder="Composition (optional)" value={composition} onChange={(e) => setComposition(e.target.value)} style={{ flex: 1, minWidth: 160, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
          <input type="number" placeholder="Qty" value={quantity} onChange={(e) => setQuantity(e.target.value)} style={{ width: 90, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
        </div>
        <input placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} style={{ width: "100%", marginBottom: 12, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
        <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Posting..." : "Post listing"}</button>
        {error && <span style={{ color: "var(--danger)", fontSize: 12.5, marginLeft: 10 }}>{error}</span>}
      </form>
    </div>
  );
}

function ListingCard({ listing, nodes, selfNode, onChanged }) {
  const meta = TYPE_META[listing.listing_type] || { label: listing.listing_type, icon: <NetworkIcon size={16} />, badge: "manual" };
  const statusMeta = STATUS_META[listing.status] || { label: listing.status, color: "var(--text-muted)" };
  const [claimingNodeId, setClaimingNodeId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const isMine = selfNode && listing.pharmacy_node_id === selfNode.id;
  const otherNodes = nodes.filter((n) => n.id !== listing.pharmacy_node_id);

  async function handleClaim() {
    if (!claimingNodeId) return;
    setBusy(true); setError(null);
    try {
      await api.claimNetworkListing(listing.id, Number(claimingNodeId));
      onChanged();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  async function handleFulfill() {
    setBusy(true); setError(null);
    try {
      await api.fulfillNetworkListing(listing.id);
      onChanged();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  async function handleWithdraw() {
    setBusy(true); setError(null);
    try {
      await api.withdrawNetworkListing(listing.id);
      onChanged();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  return (
    <div className="network-listing-card" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
      <div className="flex-between" style={{ alignItems: "flex-start" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14.5, display: "flex", alignItems: "center", gap: 6, color: "var(--text-main)" }}>
            <span style={{ color: "var(--primary-500)" }}>{meta.icon}</span> {listing.medicine_name}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            {listing.pharmacy_shop_name} {isMine && "(you)"}
            {listing.quantity != null && ` · Qty ${listing.quantity}`}
            {listing.expiry_date && ` · exp ${listing.expiry_date}`}
          </div>
          {listing.note && <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>{listing.note}</div>}
        </div>
        <div style={{ textAlign: "right" }}>
          <span className={`badge ${meta.badge}`} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>{meta.label}</span>
          <div style={{ fontSize: 11, fontWeight: 700, color: statusMeta.color, marginTop: 6, textTransform: "uppercase", display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4 }}>
            {statusMeta.icon} {statusMeta.label}
          </div>
        </div>
      </div>

      {listing.status === "claimed" && listing.claimed_by_shop_name && (
        <div className="network-claimed-note" style={{ background: "rgba(202, 138, 4, 0.1)", color: "var(--warning)" }}>
          Claimed by {listing.claimed_by_shop_name}
        </div>
      )}

      {error && <p style={{ color: "var(--danger)", fontSize: 12, marginTop: 6 }}>{error}</p>}

      <div className="network-listing-actions">
        {listing.status === "open" && !isMine && (
          <>
            <select value={claimingNodeId} onChange={(e) => setClaimingNodeId(e.target.value)} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-card)", color: "var(--text-main)", fontSize: 13 }}>
              <option value="">Claim as...</option>
              {otherNodes.map((n) => <option key={n.id} value={n.id}>{n.shop_name}{n.is_self ? " (you)" : ""}</option>)}
            </select>
            <button className="btn btn-secondary" onClick={handleClaim} disabled={busy || !claimingNodeId} style={{ padding: "6px 12px", fontSize: 13 }}>Claim</button>
          </>
        )}
        {listing.status === "open" && isMine && (
          <button className="btn btn-secondary" onClick={handleWithdraw} disabled={busy} style={{ padding: "6px 12px", fontSize: 13 }}>Withdraw</button>
        )}
        {listing.status === "claimed" && isMine && (
          <button className="btn btn-primary" onClick={handleFulfill} disabled={busy} style={{ padding: "6px 12px", fontSize: 13 }}>Mark fulfilled</button>
        )}
      </div>
    </div>
  );
}

export default function Network({ isOwner = false }) {
  const [nodes, setNodes] = useState([]);
  const [listings, setListings] = useState([]);
  const [statusFilter, setStatusFilter] = useState("open");
  const [typeFilter, setTypeFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [publishMsg, setPublishMsg] = useState(null);

  const selfNode = nodes.find((n) => n.is_self);

  function refresh() {
    setLoading(true);
    Promise.all([api.getNetworkNodes(), api.getNetworkListings(typeFilter, statusFilter)])
      .then(([n, l]) => { setNodes(n); setListings(l); })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [statusFilter, typeFilter]);

  async function handlePublish() {
    setPublishing(true);
    setPublishMsg(null);
    try {
      const created = await api.publishNearExpiryListings(60);
      setPublishMsg(`Published ${created.length} near-expiry listing(s) from your Expiry Tracker.`);
      refresh();
    } finally { setPublishing(false); }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="page-content"
    >
      <div className="card">
        <h2 style={{ marginBottom: 4, display: "flex", alignItems: "center", gap: 8, color: "var(--text-main)" }}>
          <NetworkIcon size={24} color="var(--primary-500)" /> Inter-Pharmacy Network
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 0 }}>
          Near-expiry stock, excess stock, and shortages — shared across participating pharmacies
          instead of thrown away or reordered from scratch. Claims and fulfillments between
          different shops are logged to TrustChain (see the 🔗 TrustChain screen).
        </p>
        <div className="flex-between" style={{ marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "center" }}>
            <button className="btn btn-secondary" onClick={handlePublish} disabled={publishing} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Clock size={16} />
              {publishing ? "Publishing..." : "Publish my near-expiry batches"}
            </button>
            {publishMsg && <span style={{ marginLeft: 12, fontSize: 12.5, color: "var(--success)" }}>{publishMsg}</span>}
          </div>
        </div>
      </div>

      <NodesPanel isOwner={isOwner} nodes={nodes} selfNode={selfNode} onRefresh={refresh} />
      <PostListingForm onPosted={refresh} />

      <div className="card">
        <div className="flex-between" style={{ marginBottom: 12 }}>
          <h3 style={{ margin: 0, color: "var(--text-main)" }}>Listings</h3>
          <div style={{ display: "flex", gap: 10 }}>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)", fontSize: 13 }}>
              <option value="">All types</option>
              {Object.entries(TYPE_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)", fontSize: 13 }}>
              {Object.entries(STATUS_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
            </select>
          </div>
        </div>

        {loading && <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading...</p>}
        {!loading && listings.length === 0 && <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No listings match this filter.</p>}

        <div className="network-listings-grid">
          {listings.map((l) => (
            <ListingCard key={l.id} listing={l} nodes={nodes} selfNode={selfNode} onChanged={refresh} />
          ))}
        </div>
      </div>

      <style>{`
        .network-listings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
        .network-listing-card { border: 1px solid; border-radius: 12px; padding: 14px; }
        .network-claimed-note { font-size: 12px; padding: 6px 10px; border-radius: 8px; margin-top: 10px; }
        .network-listing-actions { display: flex; gap: 8px; margin-top: 12px; align-items: center; }
      `}</style>
    </motion.div>
  );
}