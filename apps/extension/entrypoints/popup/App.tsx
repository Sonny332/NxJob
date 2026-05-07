import { useEffect, useState } from "react";

import {
  analyzeSponsorship,
  captureJobLead,
  checkHealth,
  type CaptureJobLeadResponse,
  type SponsorshipAnalyzeResponse,
  type SponsorshipStatus
} from "../../src/lib/api-client";
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
  const [sponsorshipResult, setSponsorshipResult] = useState<SponsorshipAnalyzeResponse | null>(null);
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
    setSponsorshipResult(null);

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

      if (action === "Analyze Sponsorship") {
        const sponsorship = await analyzeSponsorship(result.job_lead, context);
        setSponsorshipResult(sponsorship);
        setMessage(`Sponsorship analysis completed for ${result.job_lead.id}.`);
        return;
      }

      setMessage(`${action} captured JobLead ${result.job_lead.id}. Workflow execution starts in a later milestone.`);
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
            {activeAction === action ? actionProgressLabel(action) : action}
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

      {sponsorshipResult ? (
        <section className="sponsorship" aria-label="Sponsorship analysis result">
          <div className="sponsorship-header">
            <div>
              <strong>Sponsorship</strong>
              <span>{sponsorshipLabel(sponsorshipResult.sponsorship.status)}</span>
            </div>
            <span className={`status-pill status-pill-${sponsorshipResult.sponsorship.status}`}>
              {Math.round(sponsorshipResult.sponsorship.confidence * 100)}%
            </span>
          </div>

          <p>{sponsorshipResult.sponsorship.summary}</p>
          <small>{sponsorshipResult.ai_used ? "AI fallback" : "Local rule"} - Not a legal conclusion</small>

          <div className="evidence-list">
            <strong>Evidence</strong>
            {sponsorshipResult.evidence.map((item, index) => (
              <article key={`${item.source}-${index}`}>
                <span>{item.source}</span>
                <p>{item.evidence_text}</p>
              </article>
            ))}
          </div>

          {sponsorshipResult.sponsorship.questions_to_confirm.length > 0 ? (
            <div className="questions">
              <strong>Confirm</strong>
              <ul>
                {sponsorshipResult.sponsorship.questions_to_confirm.map((question) => (
                  <li key={question}>{question}</li>
                ))}
              </ul>
            </div>
          ) : null}
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

function actionProgressLabel(action: ActionName): string {
  return action === "Analyze Sponsorship" ? "Analyzing..." : "Capturing...";
}

function sponsorshipLabel(status: SponsorshipStatus): string {
  const labels: Record<SponsorshipStatus, string> = {
    supports: "Supports",
    does_not_support: "Does not support",
    likely_supports: "Likely supports",
    likely_not_supports: "Likely does not support",
    needs_confirmation: "Needs confirmation",
    unknown: "Unknown"
  };
  return labels[status];
}

