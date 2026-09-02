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
        setStatus("Please sign in at goodcart.com first.");
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
    <div style={{ width: 320, padding: 20, fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 22, fontWeight: 400, fontFamily: "Georgia, serif", margin: 0 }}>
        GoodCart
      </h1>
      <p style={{ fontSize: 13, color: "#6b6b6b", marginTop: 12, marginBottom: 20, lineHeight: 1.5 }}>
        Save food products to your creator storefront and earn commission.
      </p>
      <button
        onClick={saveCurrentPage}
        disabled={loading}
        style={{
          width: "100%",
          padding: "12px 16px",
          backgroundColor: "#0a0a0a",
          color: "white",
          border: "none",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          cursor: loading ? "wait" : "pointer",
          opacity: loading ? 0.7 : 1,
        }}
      >
        {loading ? "Saving..." : "Save to GoodCart"}
      </button>
      {status && (
        <p
          style={{
            marginTop: 12,
            fontSize: 12,
            color: status.startsWith("Saved") ? "#0a0a0a" : "#dc2626",
          }}
        >
          {status}
        </p>
      )}
    </div>
  );
}

export default IndexPopup;
