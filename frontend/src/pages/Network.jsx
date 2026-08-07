import { useEffect, useState } from "react";
import { api } from "../api/client.js";

const TYPE_META = {
  near_expiry: { label: "Near expiry", icon: "⏳", badge: "unmatched" },
  excess_stock: { label: "Excess stock", icon: "📦", badge: "auto" },
  shortage_request: { label: "Shortage request", icon: "🙋", badge: "manual" },
};

const STATUS_META = {
  open: { label: "Open", color: "#0284c7" },
  claimed: { label: "Claimed", color: "#ca8a04" },
  fulfilled: { label: "Fulfilled", color: "#16a34a" },
  withdrawn: { label: "Withdrawn", color: "#888" },
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
      <h3 style={{ marginTop: 0 }}>🏪 Participating pharmacies</h3>
      <p style={{ color: "#666", fontSize: 12.5 }}>
        Each row here stands in for a separately-deployed shop in a real multi-pharmacy rollout —
        for this project, other participating shops are modeled as rows you can add below. See
        the module docstring in <code>network_service.py</code> for the full honest scoping note.
      </p>
      <table>
        <thead><tr><th>Shop</th><th>Contact</th><th></th></tr></thead>
        <tbody>
          {nodes.map((n) => (
            <tr key={n.id}>
              <td>{n.shop_name} {n.is_self && <span className="badge auto" style={{ marginLeft: 6 }}>this shop</span>}</td>
              <td style={{ color: "#888" }}>{n.contact_phone || "—"}</td>
              <td></td>
            </tr>
          ))}
        </tbody>
      </table>
      {isOwner && (
        <form onSubmit={handleAdd} style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <input placeholder="Nearby pharmacy name" value={shopName} onChange={(e) => setShopName(e.target.value)} required style={{ flex: 1 }} />
          <input placeholder="Contact phone (optional)" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} style={{ width: 160 }} />
          <button type="submit" disabled={saving}>{saving ? "Adding..." : "Add pharmacy"}</button>
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
      <h3 style={{ marginTop: 0 }}>📮 Post a listing</h3>
      <form onSubmit={handleSubmit}>
        <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
          <select value={listingType} onChange={(e) => setListingType(e.target.value)}>
            <option value="excess_stock">Excess stock (I have too much)</option>
            <option value="shortage_request">Shortage request (I need this)</option>
          </select>
          <input placeholder="Medicine name" value={medicineName} onChange={(e) => setMedicineName(e.target.value)} required style={{ flex: 1, minWidth: 160 }} />
          <input placeholder="Composition (optional)" value={composition} onChange={(e) => setComposition(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
          <input type="number" placeholder="Qty" value={quantity} onChange={(e) => setQuantity(e.target.value)} style={{ width: 90 }} />
        </div>
        <input placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
        <button type="submit" disabled={saving}>{saving ? "Posting..." : "Post listing"}</button>
        {error && <span style={{ color: "#b91c1c", fontSize: 12.5, marginLeft: 10 }}>{error}</span>}
      </form>
    </div>
  );
}

function ListingCard({ listing, nodes, selfNode, onChanged }) {
  const meta = TYPE_META[listing.listing_type] || { label: listing.listing_type, icon: "🔗", badge: "manual" };
  const statusMeta = STATUS_META[listing.status] || { label: listing.status, color: "#666" };
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
    <div className="network-listing-card">
      <div className="flex-between" style={{ alignItems: "flex-start" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14.5 }}>{meta.icon} {listing.medicine_name}</div>
          <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>
            {listing.pharmacy_shop_name} {isMine && "(you)"}
            {listing.quantity != null && ` · Qty ${listing.quantity}`}
            {listing.expiry_date && ` · exp ${listing.expiry_date}`}
          </div>
          {listing.note && <div style={{ fontSize: 12, color: "#555", marginTop: 4 }}>{listing.note}</div>}
        </div>
        <div style={{ textAlign: "right" }}>
          <span className={`badge ${meta.badge}`}>{meta.label}</span>
          <div style={{ fontSize: 11, fontWeight: 700, color: statusMeta.color, marginTop: 4, textTransform: "uppercase" }}>
            {statusMeta.label}
          </div>
        </div>
      </div>

      {listing.status === "claimed" && listing.claimed_by_shop_name && (
        <div className="network-claimed-note">Claimed by {listing.claimed_by_shop_name}</div>
      )}

      {error && <p style={{ color: "#b91c1c", fontSize: 12, marginTop: 6 }}>{error}</p>}

      <div className="network-listing-actions">
        {listing.status === "open" && !isMine && (
          <>
            <select value={claimingNodeId} onChange={(e) => setClaimingNodeId(e.target.value)}>
              <option value="">Claim as...</option>
              {otherNodes.map((n) => <option key={n.id} value={n.id}>{n.shop_name}{n.is_self ? " (you)" : ""}</option>)}
            </select>
            <button className="secondary" onClick={handleClaim} disabled={busy || !claimingNodeId}>Claim</button>
          </>
        )}
        {listing.status === "open" && isMine && (
          <button className="secondary" onClick={handleWithdraw} disabled={busy}>Withdraw</button>
        )}
        {listing.status === "claimed" && isMine && (
          <button onClick={handleFulfill} disabled={busy}>Mark fulfilled</button>
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
    <div>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>🌐 Inter-Pharmacy Network</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          Near-expiry stock, excess stock, and shortages — shared across participating pharmacies
          instead of thrown away or reordered from scratch. Claims and fulfillments between
          different shops are logged to TrustChain (see the 🔗 TrustChain screen).
        </p>
        <div className="flex-between">
          <div>
            <button onClick={handlePublish} disabled={publishing}>
              {publishing ? "Publishing..." : "⏳ Publish my near-expiry batches"}
            </button>
            {publishMsg && <span style={{ marginLeft: 10, fontSize: 12.5, color: "#16a34a" }}>{publishMsg}</span>}
          </div>
        </div>
      </div>

      <NodesPanel isOwner={isOwner} nodes={nodes} selfNode={selfNode} onRefresh={refresh} />
      <PostListingForm onPosted={refresh} />

      <div className="card">
        <div className="flex-between" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>Listings</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">All types</option>
              {Object.entries(TYPE_META).map(([k, m]) => <option key={k} value={k}>{m.icon} {m.label}</option>)}
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              {Object.entries(STATUS_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
            </select>
          </div>
        </div>

        {loading && <p style={{ color: "#888", fontSize: 13 }}>Loading...</p>}
        {!loading && listings.length === 0 && <p style={{ color: "#888", fontSize: 13 }}>No listings match this filter.</p>}

        <div className="network-listings-grid">
          {listings.map((l) => (
            <ListingCard key={l.id} listing={l} nodes={nodes} selfNode={selfNode} onChanged={refresh} />
          ))}
        </div>
      </div>

      <style>{`
        .network-listings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
        .network-listing-card { border: 1px solid #e5e5e5; border-radius: 12px; padding: 14px; background: #fff; }
        .network-claimed-note { font-size: 12px; color: #92400e; background: #fef3c7; padding: 6px 10px; border-radius: 8px; margin-top: 8px; }
        .network-listing-actions { display: flex; gap: 8px; margin-top: 10px; align-items: center; }
      `}</style>
    </div>
  );
}