import { useEffect, useState } from "react";

import { captureJobLead, checkHealth, type CaptureJobLeadResponse } from "../../src/lib/api-client";
import { captureActiveTabContext, type PageContext } from "../../src/lib/page-capture";

type ServiceState = "checking" | "online" | "offline";
type ActionName = (typeof ACTIONS)[number];

const ACTIONS = [
  "Analyze Sponsorship",
  "Tailor Resume",
  "Fill Form Answer"
] as const;

export function App() {
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [pageContext, setPageContext] = useState<PageContext | null>(null);
  const [captureResult, setCaptureResult] = useState<CaptureJobLeadResponse | null>(null);
  const [activeAction, setActiveAction] = useState<ActionName | null>(null);
  const [message, setMessage] = useState("Ready.");

  useEffect(() => {
    let cancelled = false;

    refreshServiceState()
      .then((online) => {
        if (!cancelled) setServiceState(online ? "online" : "offline");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleAction(action: ActionName) {
    setActiveAction(action);
    setCaptureResult(null);

    try {
      const context = await captureActiveTabContext();
      setPageContext(context);

      const online = await refreshServiceState();
      setServiceState(online ? "online" : "offline");

      if (!online) {
        setMessage("NxJob local service is offline. Start the local service, then retry.");
        return;
      }

      const result = await captureJobLead(context);
      setCaptureResult(result);
      setMessage(`${action} captured JobLead ${result.job_lead.id}. Workflow execution starts in the next milestone.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to capture page context.");
    } finally {
      setActiveAction(null);
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
          <button
            key={action}
            type="button"
            disabled={activeAction !== null}
            onClick={() => handleAction(action)}
          >
            {activeAction === action ? "Capturing..." : action}
          </button>
        ))}
      </section>

      <section className="context" aria-label="Current page context">
        <strong>Current page</strong>
        <p>{pageContext?.title ?? "No page captured yet."}</p>
        {pageContext ? <small>{pageContext.url}</small> : null}
        {pageContext ? (
          <dl>
            <div>
              <dt>Selected</dt>
              <dd>{pageContext.selectedText.length} chars</dd>
            </div>
            <div>
              <dt>Page text</dt>
              <dd>{pageContext.pageTextExcerpt.length} chars</dd>
            </div>
          </dl>
        ) : null}
      </section>

      {captureResult ? (
        <section className="result" aria-label="Capture result">
          <strong>Captured JobLead</strong>
          <p>{captureResult.job_lead.id}</p>
          <small>
            {captureResult.dedupe.is_duplicate
              ? `Duplicate of ${captureResult.dedupe.existing_job_lead_id}`
              : "New record"}
          </small>
        </section>
      ) : null}

      <p className="message">{message}</p>
    </main>
  );
}

async function refreshServiceState(): Promise<boolean> {
  try {
    await checkHealth();
    return true;
  } catch {
    return false;
  }
}

