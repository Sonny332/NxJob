import { useEffect, useState } from "react";

import { checkHealth } from "../../src/lib/api-client";
import { captureActiveTabContext, type PageContext } from "../../src/lib/page-capture";

type ServiceState = "checking" | "online" | "offline";

const ACTIONS = [
  "Analyze Sponsorship",
  "Tailor Resume",
  "Fill Form Answer"
] as const;

export function App() {
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [pageContext, setPageContext] = useState<PageContext | null>(null);
  const [message, setMessage] = useState("Ready.");

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

  async function handleAction(action: (typeof ACTIONS)[number]) {
    try {
      const context = await captureActiveTabContext();
      setPageContext(context);
      setMessage(`${action} captured current page context. Workflow wiring starts after M2.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to capture page context.");
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

      <section className="actions" aria-label="NxJob actions">
        {ACTIONS.map((action) => (
          <button key={action} type="button" onClick={() => handleAction(action)}>
            {action}
          </button>
        ))}
      </section>

      <section className="context" aria-label="Current page context">
        <strong>Current page</strong>
        <p>{pageContext?.title ?? "No page captured yet."}</p>
        {pageContext ? <small>{pageContext.url}</small> : null}
      </section>

      <p className="message">{message}</p>
    </main>
  );
}

