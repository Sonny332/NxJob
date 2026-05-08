import { useEffect, useState } from "react";
import { browser } from "wxt/browser";

import { checkHealth } from "../../src/lib/api-client";

type ServiceState = "checking" | "online" | "offline";

export function App() {
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [message, setMessage] = useState("Open the side panel to work across tabs.");

  useEffect(() => {
    let cancelled = false;

    checkHealth()
      .then(() => {
        if (!cancelled) setServiceState("online");
      })
      .catch(() => {
        if (!cancelled) setServiceState("offline");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function openPanel() {
    try {
      const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (!tab?.windowId) {
        setMessage("No active browser window is available.");
        return;
      }

      await chrome.sidePanel.open({ windowId: tab.windowId });
      window.close();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to open NxJob side panel.");
    }
  }

  return (
    <main className="shell">
      <header className="header">
        <div>
          <h1>NxJob</h1>
          <p>Job application copilot</p>
        </div>
        <span className={`status status-${serviceState}`}>{serviceState}</span>
      </header>

      <button type="button" onClick={openPanel}>
        Open NxJob Panel
      </button>

      {serviceState === "offline" ? (
        <p className="message">NxJob local service is offline. Start the local service, then open the panel.</p>
      ) : (
        <p className="message">{message}</p>
      )}
    </main>
  );
}
