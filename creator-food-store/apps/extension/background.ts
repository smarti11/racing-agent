chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "SAVE_PRODUCT") {
    chrome.storage.local.set({ pendingSave: message });
    chrome.action.openPopup();
    sendResponse({ success: true });
  }
});
