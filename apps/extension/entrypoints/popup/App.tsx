import { useEffect, useState } from "react";

import {
  analyzeSponsorship,
  captureJobLead,
  checkHealth,
  draftFormAnswer,
  tailorResume,
  type CaptureJobLeadResponse,
  type FormAnswerDraftResponse,
  type ResumeTailorResponse,
  type SponsorshipAnalyzeResponse,
  type SponsorshipStatus
} from "../../src/lib/api-client";
import {
  captureActiveFieldContext,
  captureActiveTabContext,
  fillActiveField,
  type PageContext
} from "../../src/lib/page-capture";

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
  const [resumeResult, setResumeResult] = useState<ResumeTailorResponse | null>(null);
  const [formAnswerResult, setFormAnswerResult] = useState<FormAnswerDraftResponse | null>(null);
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
    setResumeResult(null);
    setFormAnswerResult(null);

    try {
      const fieldContext = action === "Fill Form Answer" ? await captureActiveFieldContext() : null;
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

      if (action === "Tailor Resume") {
        const resume = await tailorResume(result.job_lead);
        setResumeResult(resume);
        setMessage(`Resume generated: ${resume.resume_version.id}.`);
        return;
      }

      if (action === "Fill Form Answer") {
        if (!fieldContext) {
          setMessage("Focus a form field first, then retry Fill Form Answer.");
          return;
        }
        const draft = await draftFormAnswer(result.job_lead, fieldContext);
        setFormAnswerResult(draft);
        setMessage("Draft generated. Review before filling the field.");
        return;
      }

      setMessage(`${action} captured JobLead ${result.job_lead.id}. Workflow execution starts in a later milestone.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to capture page context.");
    } finally {
      setActiveAction(null);
    }
  }

  async function confirmFill(answer: string) {
    try {
      await fillActiveField(answer);
      setMessage("Filled current field. Review the page before submitting.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to fill current field.");
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

      {resumeResult ? (
        <section className="result" aria-label="Tailored resume result">
          <strong>Tailored Resume</strong>
          <p>{resumeResult.resume_version.id}</p>
          <small>{resumeResult.resume_version.file_path}</small>
          <small>{resumeResult.resume_version.change_summary}</small>
        </section>
      ) : null}

      {formAnswerResult ? (
        <section className="draft" aria-label="Form answer draft">
          <strong>Answer Draft</strong>
          <p>{formAnswerResult.draft.answer}</p>
          <small>{formAnswerResult.ai_used ? "AI draft" : "Fixed profile answer"} - Requires review</small>
          {formAnswerResult.draft.risk_flags.length > 0 ? (
            <ul>
              {formAnswerResult.draft.risk_flags.map((flag) => (
                <li key={flag}>{flag}</li>
              ))}
            </ul>
          ) : null}
          <button type="button" className="secondary" onClick={() => confirmFill(formAnswerResult.draft.answer)}>
            Fill Current Field
          </button>
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
  if (action === "Analyze Sponsorship") return "Analyzing...";
  if (action === "Tailor Resume") return "Tailoring...";
  if (action === "Fill Form Answer") return "Drafting...";
  return "Capturing...";
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

