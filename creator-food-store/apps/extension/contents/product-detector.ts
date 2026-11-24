import type { PlasmoCSConfig } from "plasmo";
import { identifyRetailer, isGroceryRetailer, isConsumableProduct } from "@repo/affiliate-engine";

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
  if (document.getElementById("goodcart-save-btn")) return;

  try {
    const identified = identifyRetailer(new URL(window.location.href));
    if (!identified || !isGroceryRetailer(identified.retailer)) return;
    if (!isConsumableProduct(new URL(window.location.href), document.title)) return;

    const btn = document.createElement("button");
    btn.id = "goodcart-save-btn";
    btn.textContent = "Save to GoodCart";
    btn.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 99999;
      padding: 12px 20px;
      background: #0a0a0a;
      color: white;
      border: none;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      cursor: pointer;
      font-family: system-ui, sans-serif;
    `;

    btn.addEventListener("click", () => {
      chrome.runtime.sendMessage({
        type: "SAVE_PRODUCT",
        url: window.location.href,
        title: document.title,
      });
      btn.textContent = "Opening GoodCart...";
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
