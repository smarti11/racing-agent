import { useState } from "react";
import { identifyRetailer, isFoodRetailer } from "@repo/affiliate-engine";

const API_URL = process.env.PLASMO_PUBLIC_API_URL ?? "http://localhost:3000";

function IndexPopup() {
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function saveCurrentPage() {
    setLoading(true);
    setStatus("");

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.url) {
        setStatus("No active tab found");
        return;
      }

      const url = new URL(tab.url);
      const identified = identifyRetailer(url);

      if (!identified || !isFoodRetailer(identified.retailer)) {
        setStatus("This page is not a supported food retailer.");
        return;
      }

      const token = (await chrome.storage.local.get("authToken")).authToken;
      if (!token) {
        setStatus("Please sign in at pantrylink.com first.");
        return;
      }

      const res = await fetch(`${API_URL}/api/links/monetize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: token,
        },
        credentials: "include",
        body: JSON.stringify({
          url: tab.url,
          titleHint: tab.title,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setStatus(data.error ?? "Failed to save product");
        return;
      }

      setStatus(
        `Saved! Commission: ${(data.commissionRate * 100).toFixed(0)}% — ${data.trackedLink}`
      );
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Error saving product");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ width: 320, padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 24 }}>🥗</span>
        <h1 style={{ fontSize: 18, fontWeight: "bold", margin: 0 }}>PantryLink</h1>
      </div>
      <p style={{ fontSize: 13, color: "#78716c", marginBottom: 16 }}>
        Save food products to your creator storefront and earn commission.
      </p>
      <button
        onClick={saveCurrentPage}
        disabled={loading}
        style={{
          width: "100%",
          padding: "10px 16px",
          backgroundColor: "#059669",
          color: "white",
          border: "none",
          borderRadius: 8,
          fontWeight: 600,
          cursor: loading ? "wait" : "pointer",
          opacity: loading ? 0.7 : 1,
        }}
      >
        {loading ? "Saving..." : "Save to PantryLink"}
      </button>
      {status && (
        <p
          style={{
            marginTop: 12,
            fontSize: 12,
            color: status.startsWith("Saved") ? "#059669" : "#dc2626",
          }}
        >
          {status}
        </p>
      )}
      <p style={{ marginTop: 16, fontSize: 10, color: "#a8a29e" }}>
        Supports Amazon, Walmart, Instacart, Thrive Market, iHerb, Vitacost, Target
      </p>
    </div>
  );
}

export default IndexPopup;
