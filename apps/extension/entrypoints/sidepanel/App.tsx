import { ChangeEvent, useEffect, useMemo, useState } from "react";

import {
  captureJobLead,
  checkConfigStatus,
  checkHealth,
  clearAiProvider,
  draftFormAnswer,
  getJobLead,
  getWorkflowResults,
  saveAiProvider,
  saveMasterResume,
  submitResumeFeedback,
  type ConfigStatusResponse,
  type FormAnswerDraftResponse,
  type JobLeadRecord,
  type ResumeFeedbackRating,
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
import {
  createWorkspaceRecord,
  loadWorkspaceState,
  saveWorkspaceState,
  updateWorkspaceJob,
  upsertWorkspaceJob,
  type JobWorkspaceRecord,
  type WorkspaceState
} from "../../src/lib/workspace-state";
import type { WorkflowMessageResponse } from "../../src/lib/workflow-messages";

type ServiceState = "checking" | "online" | "offline";
type WorkflowKey = "sponsorship" | "resume" | "formAnswer";

const FEEDBACK_LABELS: Record<ResumeFeedbackRating, string> = {
  good_fit: "Good fit",
  needs_stronger_match: "Needs stronger match",
  too_generic: "Too generic",
  success_reference_candidate: "Save as success reference candidate"
};

export function App() {
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [config, setConfig] = useState<ConfigStatusResponse | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceState>({ focusedJobId: "", jobs: [] });
  const [pageContext, setPageContext] = useState<PageContext | null>(null);
  const [message, setMessage] = useState("Ready.");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiProvider, setApiProvider] = useState("openai_compatible");
  const [apiBaseUrl, setApiBaseUrl] = useState("");
  const [apiModel, setApiModel] = useState("");
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    let cancelled = false;

    loadWorkspaceState().then((state) => {
      if (!cancelled) setWorkspace(state);
    });
    refreshServiceAndConfig();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    void saveWorkspaceState(workspace);
  }, [workspace]);

  useEffect(() => {
    if (config && (!config.master_resume_configured || !config.ai_provider_configured)) {
      setSettingsOpen(true);
    }
  }, [config]);

  const focusedJob = useMemo(
    () => workspace.jobs.find((job) => job.id === workspace.focusedJobId) ?? workspace.jobs[0] ?? null,
    [workspace]
  );

  async function refreshServiceAndConfig() {
    try {
      await checkHealth();
      setServiceState("online");
      const status = await checkConfigStatus();
      setConfig(status);
    } catch (error) {
      setServiceState("offline");
      setMessage(error instanceof Error ? error.message : "NxJob local service is offline.");
    }
  }

  async function captureCurrentJob() {
    try {
      setMessage("Capturing current tab...");
      const context = await captureActiveTabContext();
      setPageContext(context);
      const capture = await captureJobLead(context);
      const canonicalJob = capture.dedupe.existing_job_lead_id
        ? await getJobLead(capture.dedupe.existing_job_lead_id)
        : capture.job_lead;
      const nextRecord = createWorkspaceRecord({
        jobLead: canonicalJob,
        pageTitle: context.title,
        pageUrl: context.url,
        selectedTextLength: context.selectedText.length,
        pageTextLength: context.pageTextExcerpt.length
      });
      const hydratedRecord = await hydrateWorkflowResults(nextRecord);

      setWorkspace((current) => upsertWorkspaceJob(current, hydratedRecord));
      setMessage(capture.dedupe.is_duplicate ? "Existing JobLead restored from cache." : "Current job captured.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to capture current job.");
    }
  }

  async function runSponsorship(job: JobWorkspaceRecord, forceRefresh = false) {
    if (job.workflows.sponsorship.status === "running") {
      setMessage("Sponsorship analysis is already running for this job.");
      return;
    }

    markWorkflow(job.id, "sponsorship", "running");
    try {
      const response = await chrome.runtime.sendMessage({
        type: "NXJOB_RUN_SPONSORSHIP",
        jobLead: job.jobLead,
        forceRefresh
      }) as WorkflowMessageResponse;
      const nextState = await loadWorkspaceState();
      setWorkspace(nextState);
      if (!response.ok) {
        setMessage(response.error);
        return;
      }
      setMessage(
        response.result.cache.hit ? "Sponsorship result restored from cache." : "Sponsorship analysis completed."
      );
    } catch (error) {
      setWorkflowError(job.id, "sponsorship", error);
    }
  }

  async function runTailor(job: JobWorkspaceRecord, forceRefresh = false) {
    if (!config?.master_resume_configured) {
      setSettingsOpen(true);
      setMessage("Configure Master Resume before tailoring.");
      return;
    }

    if (job.workflows.resume.status === "running") {
      setMessage("Resume tailor is already running for this job.");
      return;
    }

    markWorkflow(job.id, "resume", "running");
    try {
      const response = await chrome.runtime.sendMessage({
        type: "NXJOB_RUN_TAILOR",
        jobLead: job.jobLead,
        forceRefresh
      }) as WorkflowMessageResponse;
      const nextState = await loadWorkspaceState();
      setWorkspace(nextState);
      if (!response.ok) {
        setMessage(response.error);
        return;
      }
      setMessage(response.result.cache.hit ? "Tailored resume restored from cache." : "Tailored resume generated.");
    } catch (error) {
      setWorkflowError(job.id, "resume", error);
    }
  }

  async function runFormAnswer(job: JobWorkspaceRecord) {
    markWorkflow(job.id, "formAnswer", "running");
    try {
      const fieldContext = await captureActiveFieldContext();
      const result = await draftFormAnswer(job.jobLead, fieldContext);
      setWorkflowResult(job.id, "formAnswer", result);
      setMessage("Answer draft generated. Review before filling the field.");
    } catch (error) {
      setWorkflowError(job.id, "formAnswer", error);
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

  async function handleMasterResumeFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const content = await file.text();
      const status = await saveMasterResume(content, file.name);
      setConfig(status);
      setMessage("Master Resume saved to local private config.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save Master Resume.");
    } finally {
      event.target.value = "";
    }
  }

  async function saveApiKey() {
    try {
      const status = await saveAiProvider({
        provider: apiProvider,
        baseUrl: apiBaseUrl,
        model: apiModel,
        apiKey
      });
      setConfig(status);
      setApiKey("");
      setMessage("AI provider saved to local private config.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save AI provider.");
    }
  }

  async function clearApiKey() {
    try {
      const status = await clearAiProvider();
      setConfig(status);
      setMessage("AI provider config cleared.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to clear AI provider.");
    }
  }

  async function saveFeedback(job: JobWorkspaceRecord, rating: ResumeFeedbackRating) {
    const resume = job.workflows.resume.result;
    if (!resume) return;

    try {
      await submitResumeFeedback({
        jobLeadId: job.jobLead.id,
        resumeVersionId: resume.resume_version.id,
        rating
      });
      setMessage(`Resume feedback saved: ${FEEDBACK_LABELS[rating]}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save resume feedback.");
    }
  }

  function markWorkflow(jobId: string, key: WorkflowKey, status: "running") {
    setWorkspace((current) =>
      updateWorkspaceJob(current, jobId, (job) => ({
        ...job,
        updatedAt: new Date().toISOString(),
        workflows: {
          ...job.workflows,
          [key]: {
            ...job.workflows[key],
            status,
            updatedAt: new Date().toISOString(),
            error: ""
          }
        }
      }))
    );
  }

  function setWorkflowResult(
    jobId: string,
    key: "sponsorship",
    result: SponsorshipAnalyzeResponse
  ): void;
  function setWorkflowResult(jobId: string, key: "resume", result: ResumeTailorResponse): void;
  function setWorkflowResult(jobId: string, key: "formAnswer", result: FormAnswerDraftResponse): void;
  function setWorkflowResult(
    jobId: string,
    key: WorkflowKey,
    result: SponsorshipAnalyzeResponse | ResumeTailorResponse | FormAnswerDraftResponse
  ) {
    setWorkspace((current) =>
      updateWorkspaceJob(current, jobId, (job) => ({
        ...job,
        updatedAt: new Date().toISOString(),
        workflows: {
          ...job.workflows,
          [key]: {
            status: "completed",
            updatedAt: new Date().toISOString(),
            traceId: result.trace_id,
            result,
            error: ""
          }
        }
      }))
    );
  }

  function setWorkflowError(jobId: string, key: WorkflowKey, error: unknown) {
    const messageText = error instanceof Error ? error.message : "Workflow failed.";
    setWorkspace((current) =>
      updateWorkspaceJob(current, jobId, (job) => ({
        ...job,
        updatedAt: new Date().toISOString(),
        workflows: {
          ...job.workflows,
          [key]: {
            ...job.workflows[key],
            status: "failed",
            updatedAt: new Date().toISOString(),
            error: messageText
          }
        }
      }))
    );
    setMessage(messageText);
  }

  return (
    <main className="panel-shell">
      <header className="panel-header">
        <div>
          <h1>NxJob</h1>
          <p>Side panel workspace</p>
        </div>
        <button type="button" className="ghost-button" onClick={refreshServiceAndConfig}>
          <span className={`status status-${serviceState}`}>{serviceState}</span>
        </button>
      </header>

      <section className={setupClassName(config)} aria-label="Setup">
        <div className="section-heading">
          <strong>Setup</strong>
          <button type="button" className="text-button" onClick={() => setSettingsOpen((value) => !value)}>
            {settingsOpen ? "Hide" : "Settings"}
          </button>
        </div>
        <div className="setup-status">
          <span className={config?.master_resume_configured ? "setup-ok" : "setup-needed"}>
            Master Resume {config?.master_resume_configured ? "ready" : "missing"}
          </span>
          <span className={config?.ai_provider_configured ? "setup-ok" : "setup-needed"}>
            AI Key {config?.ai_provider_configured ? "ready" : "missing"}
          </span>
        </div>

        {settingsOpen ? (
          <div className="settings-grid">
            <label className="file-input">
              <span>Update Master Resume JSON</span>
              <input type="file" accept="application/json,.json" onChange={handleMasterResumeFile} />
            </label>

            <label>
              <span>Provider</span>
              <input value={apiProvider} onChange={(event) => setApiProvider(event.target.value)} />
            </label>
            <label>
              <span>Base URL</span>
              <input value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} />
            </label>
            <label>
              <span>Model</span>
              <input value={apiModel} onChange={(event) => setApiModel(event.target.value)} />
            </label>
            <label>
              <span>API Key</span>
              <input value={apiKey} type="password" onChange={(event) => setApiKey(event.target.value)} />
            </label>
            <div className="settings-actions">
              <button type="button" onClick={saveApiKey}>
                Save AI Key
              </button>
              <button type="button" className="secondary-button" onClick={clearApiKey}>
                Clear AI Key
              </button>
            </div>
            <small>Private config is stored by the local service. Keys and resume contents are not written to logs.</small>
          </div>
        ) : null}
      </section>

      <section className="capture-strip" aria-label="Capture">
        <button type="button" onClick={captureCurrentJob}>
          Capture Current Tab
        </button>
        <div>
          <strong>{pageContext?.title ?? "No active capture yet."}</strong>
          <small>{pageContext ? `${pageContext.selectedText.length} selected chars` : "Select a JD, then capture."}</small>
        </div>
      </section>

      <section className="workspace" aria-label="Job workspace">
        <nav className="job-list" aria-label="Captured jobs">
          {workspace.jobs.length === 0 ? <p className="empty">No captured jobs yet.</p> : null}
          {workspace.jobs.map((job) => (
            <button
              key={job.id}
              type="button"
              className={job.id === focusedJob?.id ? "job-card job-card-active" : "job-card"}
              onClick={() => setWorkspace((current) => ({ ...current, focusedJobId: job.id }))}
            >
              <span>{job.jobLead.page_title || job.jobLead.job_title || "Untitled job"}</span>
              <small>{job.jobLead.source_site} · {job.selectedTextLength} selected chars</small>
              <small>{jobSummary(job)}</small>
            </button>
          ))}
        </nav>

        <div className="job-detail">
          {focusedJob ? (
            <JobDetail
              job={focusedJob}
              masterResumeReady={Boolean(config?.master_resume_configured)}
              onAnalyze={() => runSponsorship(focusedJob)}
              onAnalyzeRefresh={() => runSponsorship(focusedJob, true)}
              onTailor={() => runTailor(focusedJob)}
              onTailorRefresh={() => runTailor(focusedJob, true)}
              onDraftAnswer={() => runFormAnswer(focusedJob)}
              onFillAnswer={confirmFill}
              onFeedback={(rating) => saveFeedback(focusedJob, rating)}
            />
          ) : (
            <p className="empty">Capture a job to begin.</p>
          )}
        </div>
      </section>

      <p className="message">{message}</p>
    </main>
  );
}

function JobDetail(props: {
  job: JobWorkspaceRecord;
  masterResumeReady: boolean;
  onAnalyze: () => void;
  onAnalyzeRefresh: () => void;
  onTailor: () => void;
  onTailorRefresh: () => void;
  onDraftAnswer: () => void;
  onFillAnswer: (answer: string) => void;
  onFeedback: (rating: ResumeFeedbackRating) => void;
}) {
  const { job } = props;
  const sponsorship = job.workflows.sponsorship.result;
  const resume = job.workflows.resume.result;
  const formAnswer = job.workflows.formAnswer.result;

  return (
    <article className="detail-card">
      <header className="detail-header">
        <div>
          <h2>{job.jobLead.page_title || job.jobLead.job_title || "Captured job"}</h2>
          <p>{job.jobLead.source_url}</p>
        </div>
        <span className="id-pill">{job.jobLead.id}</span>
      </header>

      <div className="action-row">
        <button type="button" disabled={job.workflows.sponsorship.status === "running"} onClick={props.onAnalyze}>
          {job.workflows.sponsorship.status === "running" ? "Analyzing..." : "Analyze Sponsorship"}
        </button>
        <button type="button" className="secondary-button" onClick={props.onAnalyzeRefresh}>
          Re-run
        </button>
      </div>

      {sponsorship ? <SponsorshipResult result={sponsorship} /> : <WorkflowMessage run={job.workflows.sponsorship} />}

      <div className="action-row">
        <button
          type="button"
          disabled={!props.masterResumeReady || job.workflows.resume.status === "running"}
          onClick={props.onTailor}
        >
          {job.workflows.resume.status === "running" ? "Tailoring..." : "Tailor Resume"}
        </button>
        <button type="button" className="secondary-button" disabled={!props.masterResumeReady} onClick={props.onTailorRefresh}>
          Re-run
        </button>
      </div>

      {resume ? <ResumeResult result={resume} onFeedback={props.onFeedback} /> : <WorkflowMessage run={job.workflows.resume} />}

      <div className="action-row">
        <button type="button" disabled={job.workflows.formAnswer.status === "running"} onClick={props.onDraftAnswer}>
          {job.workflows.formAnswer.status === "running" ? "Drafting..." : "Fill Form Answer"}
        </button>
      </div>

      {formAnswer ? (
        <section className="result-block">
          <strong>Answer Draft</strong>
          <p>{formAnswer.draft.answer}</p>
          <small>{formAnswer.ai_used ? "AI draft" : "Fixed profile answer"} · Requires review</small>
          <button type="button" className="secondary-button" onClick={() => props.onFillAnswer(formAnswer.draft.answer)}>
            Fill Current Field
          </button>
        </section>
      ) : (
        <WorkflowMessage run={job.workflows.formAnswer} />
      )}
    </article>
  );
}

function SponsorshipResult({ result }: { result: SponsorshipAnalyzeResponse }) {
  return (
    <section className="result-block">
      <div className="result-heading">
        <div>
          <strong>Sponsorship</strong>
          <span>{sponsorshipLabel(result.sponsorship.status)}</span>
        </div>
        <span className={`status-pill status-pill-${result.sponsorship.status}`}>
          {Math.round(result.sponsorship.confidence * 100)}%
        </span>
      </div>
      <p>{result.sponsorship.summary}</p>
      <small>
        {result.ai_used ? "AI fallback" : "Local rule"} · {result.cache.hit ? "Cache hit" : "Fresh result"} · Not a legal
        conclusion
      </small>
      <div className="evidence-list">
        <strong>Evidence</strong>
        {result.evidence.map((item, index) => (
          <article key={`${item.source}-${index}`}>
            <span>{item.source}</span>
            <p>{item.evidence_text}</p>
          </article>
        ))}
      </div>
      {result.sponsorship.questions_to_confirm.length > 0 ? (
        <div className="questions">
          <strong>Confirm</strong>
          <ul>
            {result.sponsorship.questions_to_confirm.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function ResumeResult(props: {
  result: ResumeTailorResponse;
  onFeedback: (rating: ResumeFeedbackRating) => void;
}) {
  const { result } = props;
  return (
    <section className="result-block">
      <strong>Tailored Resume</strong>
      <p>{result.resume_version.file_path}</p>
      <small>{result.cache.hit ? "Cache hit" : "Fresh result"} · {result.resume_version.change_summary}</small>
      <div className="compact-list">
        <span>Selected bullets</span>
        <p>{result.resume_version.selected_bullets.join(", ") || "None"}</p>
      </div>
      <div className="compact-list">
        <span>Success references</span>
        <p>{result.used_success_references.join(", ") || "None"}</p>
      </div>
      {result.warnings.length > 0 ? (
        <ul>
          {result.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      <div className="feedback-grid">
        {(Object.keys(FEEDBACK_LABELS) as ResumeFeedbackRating[]).map((rating) => (
          <button key={rating} type="button" className="secondary-button" onClick={() => props.onFeedback(rating)}>
            {FEEDBACK_LABELS[rating]}
          </button>
        ))}
      </div>
    </section>
  );
}

function WorkflowMessage({ run }: { run: { status: string; error: string } }) {
  if (run.status === "failed") return <p className="workflow-error">{run.error}</p>;
  if (run.status === "running") return <p className="workflow-note">Workflow is running.</p>;
  return null;
}

async function hydrateWorkflowResults(record: JobWorkspaceRecord): Promise<JobWorkspaceRecord> {
  const results = await getWorkflowResults(record.jobLead.id);
  let hydrated = record;

  for (const result of results.results.reverse()) {
    if (result.workflow_name === "analyze_sponsorship") {
      hydrated = {
        ...hydrated,
        workflows: {
          ...hydrated.workflows,
          sponsorship: {
            status: "completed",
            updatedAt: result.created_at,
            traceId: result.trace_id,
            result: result.response as SponsorshipAnalyzeResponse,
            error: ""
          }
        }
      };
    }

    if (result.workflow_name === "tailor_resume") {
      hydrated = {
        ...hydrated,
        workflows: {
          ...hydrated.workflows,
          resume: {
            status: "completed",
            updatedAt: result.created_at,
            traceId: result.trace_id,
            result: result.response as ResumeTailorResponse,
            error: ""
          }
        }
      };
    }
  }

  return hydrated;
}

function setupClassName(config: ConfigStatusResponse | null): string {
  if (!config || !config.master_resume_configured || !config.ai_provider_configured) {
    return "setup setup-attention";
  }
  return "setup";
}

function jobSummary(job: JobWorkspaceRecord): string {
  const sponsorship = job.workflows.sponsorship.result;
  const resume = job.workflows.resume.result;
  const sponsorshipText = sponsorship ? sponsorshipLabel(sponsorship.sponsorship.status) : "No sponsorship result";
  const resumeText = resume ? "Resume ready" : "No resume";
  return `${sponsorshipText} · ${resumeText}`;
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
