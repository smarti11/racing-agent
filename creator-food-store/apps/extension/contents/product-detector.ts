import type { PlasmoCSConfig } from "plasmo";
import { identifyRetailer, isFoodRetailer } from "@repo/affiliate-engine";

export const config: PlasmoCSConfig = {
  matches: [
    "https://www.amazon.com/*",
    "https://www.walmart.com/*",
    "https://www.instacart.com/*",
    "https://thrivemarket.com/*",
    "https://www.iherb.com/*",
    "https://www.vitacost.com/*",
    "https://www.target.com/*",
  ],
};

function injectSaveButton() {
  if (document.getElementById("pantrylink-save-btn")) return;

  try {
    const identified = identifyRetailer(new URL(window.location.href));
    if (!identified || !isFoodRetailer(identified.retailer)) return;

    const btn = document.createElement("button");
    btn.id = "pantrylink-save-btn";
    btn.textContent = "🥗 Save to PantryLink";
    btn.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 99999;
      padding: 12px 20px;
      background: #059669;
      color: white;
      border: none;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      font-family: system-ui, sans-serif;
    `;

    btn.addEventListener("click", () => {
      chrome.runtime.sendMessage({
        type: "SAVE_PRODUCT",
        url: window.location.href,
        title: document.title,
      });
      btn.textContent = "✓ Opening PantryLink...";
    });

    document.body.appendChild(btn);
  } catch {
    // Not a valid product page
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", injectSaveButton);
} else {
  injectSaveButton();
}
