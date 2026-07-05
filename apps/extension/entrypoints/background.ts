export default defineBackground(() => {
  if (chrome.sidePanel?.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {
      // The popup remains the explicit launcher when side panel behavior is unavailable.
    });
  }
});
