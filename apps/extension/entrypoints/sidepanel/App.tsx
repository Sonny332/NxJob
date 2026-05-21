import { ChangeEvent, useEffect, useMemo, useState } from "react";

import {
  activateAiProviderProfile,
  captureJobLead,
  checkConfigStatus,
  checkHealth,
  clearAiProvider,
  createApplication,
  createOutcome,
  deleteAiProviderProfile,
  draftFormAnswer,
  draftFormAnswers,
  getResumeArtifactUrl,
  getJobLead,
  getWorkflowResults,
  listAiProviderProfiles,
  listApplications,
  listOutcomes,
  listSuccessReferences,
  saveAiProvider,
  saveMasterResume,
  saveResumeOutputDirectory,
  submitResumeFeedback,
  type ApplicationMethod,
  type ApplicationRecord,
  type AiProviderProfileRecord,
  type ConfigStatusResponse,
  type FormAnswerDraftResponse,
  type FormAnswerDraftsResponse,
  type JobLeadRecord,
  type OutcomeSignalResponse,
  type OutcomeType,
  type ResumeFeedbackRating,
  type ResumeTailorResponse,
  type SponsorshipAnalyzeResponse,
  type SponsorshipStatus
} from "../../src/lib/api-client";
import {
  captureActiveFieldContext,
  captureActiveTabContext,
  fillFormFieldById,
  fillActiveField,
  listOpenTabUrls,
  scanActiveTabFormFields,
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
type TrackingStatus = "idle" | "running";
type FeedbackActionRating = Exclude<ResumeFeedbackRating, "success_reference_candidate">;
type SidePanelOutcomeType = Extract<OutcomeType, "positive_reply" | "screen" | "interview" | "rejection">;
const FEEDBACK_ACTIONS: FeedbackActionRating[] = [
  "good_fit",
  "needs_stronger_match",
  "too_generic",
  "save_success_candidate"
];
const OUTCOME_ACTIONS: SidePanelOutcomeType[] = ["positive_reply", "screen", "interview", "rejection"];

const FEEDBACK_LABELS: Record<ResumeFeedbackRating, string> = {
  good_fit: "Good fit",
  needs_stronger_match: "Needs stronger match",
  too_generic: "Too generic",
  save_success_candidate: "Save as success candidate",
  success_reference_candidate: "Save as success candidate"
};

const OUTCOME_LABELS: Record<SidePanelOutcomeType, string> = {
  positive_reply: "Positive reply",
  screen: "Screen",
  interview: "Interview",
  rejection: "Rejection"
};

function isSensitiveField(field: { sensitiveKind?: string }): boolean {
  return Boolean(field.sensitiveKind?.trim());
}

function sensitiveFieldMessage(kind?: string): string {
  const label = kind?.trim() || "sensitive";
  return `NxJob will not draft or fill ${label} fields. Complete this field manually.`;
}

const APPLICATION_STATUS_BY_OUTCOME: Record<SidePanelOutcomeType, ApplicationRecord["status"]> = {
  positive_reply: "replied",
  screen: "interviewing",
  interview: "interviewing",
  rejection: "rejected"
};

const AI_PROVIDER_PRESETS = {
  openai: {
    label: "OpenAI",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4.1-mini",
    help: "Recommended for most users with an OpenAI API key."
  },
  deepseek: {
    label: "DeepSeek",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-v4-flash",
    help: "Default DeepSeek preset, using v4 Flash for fast resume and sponsorship workflows."
  },
  deepseek_v4_flash: {
    label: "DeepSeek V4 Flash",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-v4-flash",
    help: "Use with a DeepSeek API key when speed and cost matter most."
  },
  deepseek_v4_pro: {
    label: "DeepSeek V4 Pro",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-v4-pro",
    help: "Use with a DeepSeek API key when resume quality matters more than speed."
  },
  gemini: {
    label: "Gemini",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    model: "gemini-2.5-flash-lite",
    help: "Use with a Gemini API key. Default is Flash-Lite for non-grounded resume tailoring."
  },
  gemini_grounded: {
    label: "Gemini + Google Search",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    model: "gemini-2.5-flash",
    help: "Use when a workflow needs Google Search grounding. Tailor Resume does not use grounding yet."
  },
  openrouter: {
    label: "OpenRouter",
    baseUrl: "https://openrouter.ai/api/v1",
    model: "openai/gpt-4.1-mini",
    help: "Use with an OpenRouter API key and model route."
  },
  custom: {
    label: "Custom OpenAI-compatible",
    baseUrl: "",
    model: "",
    help: "For advanced users with a compatible /chat/completions endpoint."
  }
} as const;

type AiProviderPresetKey = keyof typeof AI_PROVIDER_PRESETS;

export function App() {
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [config, setConfig] = useState<ConfigStatusResponse | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceState>({ focusedJobId: "", showHidden: false, jobs: [] });
  const [pageContext, setPageContext] = useState<PageContext | null>(null);
  const [message, setMessage] = useState("Ready.");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiProvider, setApiProvider] = useState<AiProviderPresetKey>("openai");
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(AI_PROVIDER_PRESETS.openai.baseUrl);
  const [apiModel, setApiModel] = useState<string>(AI_PROVIDER_PRESETS.openai.model);
  const [apiDisplayName, setApiDisplayName] = useState<string>(AI_PROVIDER_PRESETS.openai.label);
  const [apiReasoningEffort, setApiReasoningEffort] = useState<string>("medium");
  const [apiKey, setApiKey] = useState("");
  const [resumeOutputDir, setResumeOutputDir] = useState("");
  const [aiProfiles, setAiProfiles] = useState<AiProviderProfileRecord[]>([]);
  const [applicationsByJobId, setApplicationsByJobId] = useState<Record<string, ApplicationRecord>>({});
  const [outcomesByApplicationId, setOutcomesByApplicationId] = useState<Record<string, OutcomeSignalResponse>>({});
  const [trackingStatus, setTrackingStatus] = useState<TrackingStatus>("idle");
  const [successReferenceCount, setSuccessReferenceCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    loadWorkspaceState().then((state) => {
      if (!cancelled) {
        setWorkspace(state);
        void hydrateTrackingForJobs(state.jobs);
      }
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
    if (config && (!config.master_resume_configured || !config.ai_provider_configured || !config.resume_output_dir_configured)) {
      setSettingsOpen(true);
    }
    if (config?.resume_output_dir) {
      setResumeOutputDir(config.resume_output_dir);
    }
  }, [config]);

  useEffect(() => {
    if (serviceState === "online" && workspace.jobs.length > 0) {
      void hydrateTrackingForJobs(workspace.jobs);
    }
  }, [serviceState, workspace.jobs.length]);

  const focusedJob = useMemo(
    () => visibleJobs(workspace).find((job) => job.id === workspace.focusedJobId) ?? visibleJobs(workspace)[0] ?? null,
    [workspace]
  );

  async function refreshServiceAndConfig() {
    try {
      await checkHealth();
      setServiceState("online");
      const status = await checkConfigStatus();
      setConfig(status);
      const profiles = await listAiProviderProfiles();
      setAiProfiles(profiles.profiles);
    } catch (error) {
      setServiceState("offline");
      setMessage(error instanceof Error ? error.message : "NxJob local service is offline.");
    }
  }

  async function hydrateTrackingForJobs(jobs: JobWorkspaceRecord[]) {
    if (jobs.length === 0) return;

    try {
      const entries = await Promise.all(
        jobs.map(async (job) => {
          const [applications, outcomes] = await Promise.all([
            listApplications({ jobLeadId: job.jobLead.id, limit: 1 }),
            listOutcomes({ jobLeadId: job.jobLead.id, limit: 1 })
          ]);
          return {
            jobId: job.id,
            application: applications.applications[0] ?? null,
            outcome: outcomes.outcomes[0] ?? null
          };
        })
      );

      const applications: Record<string, ApplicationRecord> = {};
      const outcomes: Record<string, OutcomeSignalResponse> = {};
      for (const entry of entries) {
        if (entry.application) {
          applications[entry.jobId] = entry.application;
        }
        if (entry.application && entry.outcome) {
          outcomes[entry.application.id] = {
            trace_id: "",
            outcome: entry.outcome,
            success_reference: {
              created: false,
              id: ""
            }
          };
        }
      }

      if (Object.keys(applications).length > 0) {
        setApplicationsByJobId((current) => ({ ...current, ...applications }));
      }
      if (Object.keys(outcomes).length > 0) {
        setOutcomesByApplicationId((current) => ({ ...current, ...outcomes }));
      }
    } catch {
      // Tracking hydration is best-effort; capture and tailoring remain usable if local tracking reads fail.
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
      await hydrateTrackingForJobs([hydratedRecord]);

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
    if (!config?.resume_output_dir_configured) {
      setSettingsOpen(true);
      setMessage("Configure Resume Output Folder before tailoring.");
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
      const formContext = await scanActiveTabFormFields();
      const fields = formContext.fields.filter((field) => !isSensitiveField(field));
      if (fields.length === 0) {
        const fieldContext = await captureActiveFieldContext();
        if (isSensitiveField(fieldContext)) {
          const error = new Error(sensitiveFieldMessage(fieldContext.sensitiveKind));
          setWorkflowError(job.id, "formAnswer", error);
          setMessage(error.message);
          return;
        }
        const result = await draftFormAnswer(job.jobLead, fieldContext);
        setWorkflowResult(job.id, "formAnswer", result);
        setMessage("Answer draft generated for the focused field. Review before filling.");
        return;
      }
      const result = await draftFormAnswers(job.jobLead, fields);
      setWorkflowResult(job.id, "formAnswer", result);
      setMessage(`Generated ${result.drafts.length} form answer drafts. Review before filling.`);
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
        apiKey,
        displayName: apiDisplayName,
        reasoningEffort: apiReasoningEffort
      });
      setConfig(status);
      const profiles = await listAiProviderProfiles();
      setAiProfiles(profiles.profiles);
      setApiKey("");
      setMessage("AI provider profile saved to local private config.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save AI provider.");
    }
  }

  function selectAiProvider(provider: AiProviderPresetKey) {
    const preset = AI_PROVIDER_PRESETS[provider];
    setApiProvider(provider);
    setApiBaseUrl(preset.baseUrl);
    setApiModel(preset.model);
    setApiDisplayName(preset.label);
  }

  async function confirmFillField(fieldId: string, answer: string) {
    try {
      await fillFormFieldById(fieldId, answer);
      setMessage("Filled selected field. Review the page before submitting.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to fill selected field.");
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

  async function saveOutputFolder() {
    try {
      const status = await saveResumeOutputDirectory(resumeOutputDir);
      setConfig(status);
      setMessage("Resume output folder saved to local private config.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save resume output folder.");
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
      const suffix = rating === "save_success_candidate" ? " Candidate status saved; not a confirmed outcome." : "";
      setMessage(`Resume feedback saved: ${FEEDBACK_LABELS[rating]}.${suffix}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save resume feedback.");
    }
  }

  async function activateProfile(profileId: string) {
    try {
      await activateAiProviderProfile(profileId);
      await refreshServiceAndConfig();
      setMessage("AI provider profile activated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to activate AI profile.");
    }
  }

  async function removeProfile(profileId: string) {
    try {
      const status = await deleteAiProviderProfile(profileId);
      setConfig(status);
      const profiles = await listAiProviderProfiles();
      setAiProfiles(profiles.profiles);
      setMessage("AI provider profile removed.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to remove AI profile.");
    }
  }

  async function recordApplication(job: JobWorkspaceRecord, resume: ResumeTailorResponse) {
    if (trackingStatus === "running") return;

    setTrackingStatus("running");
    try {
      const response = await createApplication({
        jobLeadId: job.jobLead.id,
        resumeVersionId: resume.resume_version.id,
        applicationUrl: job.pageUrl || job.jobLead.source_url,
        applicationMethod: inferApplicationMethod(job),
        submittedByUser: true
      });
      setApplicationsByJobId((current) => ({
        ...current,
        [job.id]: response.application
      }));
      setMessage(`Application recorded: ${response.application.id} (${response.application.status}).`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to record application.");
    } finally {
      setTrackingStatus("idle");
    }
  }

  async function recordOutcome(job: JobWorkspaceRecord, application: ApplicationRecord, outcomeType: SidePanelOutcomeType) {
    if (trackingStatus === "running") return;

    setTrackingStatus("running");
    try {
      const response = await createOutcome({
        applicationId: application.id,
        jobLeadId: job.jobLead.id,
        outcomeType,
        evidenceUrl: application.application_url
      });
      setOutcomesByApplicationId((current) => ({
        ...current,
        [application.id]: response
      }));
      setApplicationsByJobId((current) => ({
        ...current,
        [job.id]: {
          ...application,
          status: APPLICATION_STATUS_BY_OUTCOME[outcomeType]
        }
      }));
      if (response.success_reference.created) {
        const references = await listSuccessReferences({ limit: 100 });
        setSuccessReferenceCount(references.success_references.length);
      }
      const suffix = response.success_reference.created
        ? ` Success reference created: ${response.success_reference.id}.`
        : "";
      setMessage(`Outcome recorded: ${OUTCOME_LABELS[outcomeType]}.${suffix}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to record outcome.");
    } finally {
      setTrackingStatus("idle");
    }
  }

  function hideJob(jobId: string) {
    setWorkspace((current) => {
      const updated = updateWorkspaceJob(current, jobId, (job) => ({
        ...job,
        visibility: "hidden",
        hiddenAt: new Date().toISOString()
      }));
      return updated.focusedJobId === jobId ? { ...updated, focusedJobId: visibleJobs(updated)[0]?.id ?? "" } : updated;
    });
  }

  function restoreJob(jobId: string) {
    setWorkspace((current) =>
      updateWorkspaceJob(current, jobId, (job) => ({
        ...job,
        visibility: "active",
        hiddenAt: ""
      }))
    );
  }

  async function refreshOpenTabs() {
    try {
      const urls = await listOpenTabUrls();
      const normalizedUrls = new Set(urls.map(normalizeUrlForPresence));
      setWorkspace((current) => ({
        ...current,
        jobs: current.jobs.map((job) => ({
          ...job,
          tabPresence: normalizedUrls.has(normalizeUrlForPresence(job.pageUrl || job.jobLead.source_url)) ? "open" : "closed",
          visibility:
            job.visibility === "hidden" || normalizedUrls.has(normalizeUrlForPresence(job.pageUrl || job.jobLead.source_url))
              ? job.visibility
              : "hidden",
          hiddenAt:
            job.visibility === "hidden" || normalizedUrls.has(normalizeUrlForPresence(job.pageUrl || job.jobLead.source_url))
              ? job.hiddenAt
              : new Date().toISOString()
        }))
      }));
      setMessage("Job cards refreshed. Closed-tab jobs were hidden from the active list.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to refresh open browser tabs.");
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
  function setWorkflowResult(jobId: string, key: "formAnswer", result: FormAnswerDraftResponse | FormAnswerDraftsResponse): void;
  function setWorkflowResult(
    jobId: string,
    key: WorkflowKey,
    result: SponsorshipAnalyzeResponse | ResumeTailorResponse | FormAnswerDraftResponse | FormAnswerDraftsResponse
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
          <span className={config?.resume_output_dir_configured ? "setup-ok" : "setup-needed"}>
            Output Folder {config?.resume_output_dir_configured ? "ready" : "missing"}
          </span>
        </div>
        {config?.ai_provider_configured ? (
          <p className="active-ai">
            AI: {config.ai_profile_display_name || config.ai_provider_name} · {config.ai_model || "model unset"} · thinking{" "}
            {config.ai_reasoning_effort || "medium"}
          </p>
        ) : null}

        {settingsOpen ? (
          <div className="settings-grid">
            <label className="file-input">
              <span>Update Master Resume JSON</span>
              <input type="file" accept="application/json,.json" onChange={handleMasterResumeFile} />
            </label>

            <label>
              <span>Profile Name</span>
              <input value={apiDisplayName} onChange={(event) => setApiDisplayName(event.target.value)} />
            </label>
            <label>
              <span>AI Service</span>
              <select value={apiProvider} onChange={(event) => selectAiProvider(event.target.value as AiProviderPresetKey)}>
                {(Object.keys(AI_PROVIDER_PRESETS) as AiProviderPresetKey[]).map((key) => (
                  <option key={key} value={key}>
                    {AI_PROVIDER_PRESETS[key].label}
                  </option>
                ))}
              </select>
              <small>{AI_PROVIDER_PRESETS[apiProvider].help}</small>
            </label>
            <label>
              <span>Base URL</span>
              <input value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} />
            </label>
            <label>
              <span>Model</span>
              <input value={apiModel} onChange={(event) => setApiModel(event.target.value)} />
              <small>Preset default is filled automatically. Advanced users may override it.</small>
            </label>
            <label>
              <span>Thinking Strength</span>
              <select value={apiReasoningEffort} onChange={(event) => setApiReasoningEffort(event.target.value)}>
                <option value="none">None</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
              <small>Saved and shown in NxJob. Providers that do not support it may ignore this setting.</small>
            </label>
            <label>
              <span>API Key</span>
              <input value={apiKey} type="password" onChange={(event) => setApiKey(event.target.value)} />
              {config?.ai_provider_configured ? (
                <small>
                  Active source: {config.ai_provider_source === "environment" ? "environment fallback" : "local private config"}
                </small>
              ) : null}
            </label>
            <label>
              <span>Resume Output Folder</span>
              <input
                value={resumeOutputDir}
                placeholder="D:\\Resume\\NxJob Generated"
                onChange={(event) => setResumeOutputDir(event.target.value)}
              />
            </label>
            <div className="settings-actions">
              <button type="button" onClick={saveApiKey}>
                Save AI Key
              </button>
              <button type="button" onClick={saveOutputFolder}>
                Save Output Folder
              </button>
              <button type="button" className="secondary-button" onClick={clearApiKey}>
                Clear AI Key
              </button>
            </div>
            {aiProfiles.length > 0 ? (
              <div className="profile-list">
                <strong>Saved AI Profiles</strong>
                {aiProfiles.map((profile) => (
                  <div key={profile.id} className="profile-row">
                    <span>
                      {profile.display_name} · {profile.model || "model unset"} · {profile.reasoning_effort}
                    </span>
                    <button type="button" className="secondary-button" disabled={profile.is_active} onClick={() => activateProfile(profile.id)}>
                      {profile.is_active ? "Active" : "Use"}
                    </button>
                    {profile.source === "private_config" ? (
                      <button type="button" className="secondary-button" onClick={() => removeProfile(profile.id)}>
                        Remove
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
            <small>
              NxJob uses local private config first. Environment variables are only a development fallback. Keys and resume contents are not written to logs.
            </small>
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
          <div className="job-list-tools">
            <button type="button" className="secondary-button" onClick={refreshOpenTabs}>
              Refresh Tabs
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => setWorkspace((current) => ({ ...current, showHidden: !current.showHidden }))}
            >
              {workspace.showHidden ? "Show Active" : "Show Hidden"}
            </button>
          </div>
          {workspace.jobs.length === 0 ? <p className="empty">No captured jobs yet.</p> : null}
          {visibleJobs(workspace).map((job) => (
            <button
              key={job.id}
              type="button"
              className={job.id === focusedJob?.id ? "job-card job-card-active" : "job-card"}
              onClick={() => setWorkspace((current) => ({ ...current, focusedJobId: job.id }))}
            >
              <span>{jobDisplayTitle(job.jobLead)}</span>
              <small>{jobDisplaySubtitle(job.jobLead)} · {job.selectedTextLength} selected chars</small>
              <small>{job.visibility === "hidden" ? "hidden" : job.tabPresence === "closed" ? "tab closed" : "active"}</small>
              <small>{jobSummary(job)}</small>
            </button>
          ))}
        </nav>

        <div className="job-detail">
          {focusedJob ? (
            <JobDetail
              job={focusedJob}
              masterResumeReady={Boolean(config?.master_resume_configured && config?.resume_output_dir_configured)}
              onAnalyze={() => runSponsorship(focusedJob)}
              onAnalyzeRefresh={() => runSponsorship(focusedJob, true)}
              onTailor={() => runTailor(focusedJob)}
              onTailorRefresh={() => runTailor(focusedJob, true)}
              onDraftAnswer={() => runFormAnswer(focusedJob)}
              onFillAnswer={confirmFill}
              onFillField={confirmFillField}
              onFeedback={(rating) => saveFeedback(focusedJob, rating)}
              onHide={() => hideJob(focusedJob.id)}
              onRestore={() => restoreJob(focusedJob.id)}
              application={applicationsByJobId[focusedJob.id] ?? null}
              outcome={applicationsByJobId[focusedJob.id] ? outcomesByApplicationId[applicationsByJobId[focusedJob.id].id] ?? null : null}
              trackingBusy={trackingStatus === "running"}
              successReferenceCount={successReferenceCount}
              onRecordApplication={(resume) => recordApplication(focusedJob, resume)}
              onRecordOutcome={(application, outcomeType) => recordOutcome(focusedJob, application, outcomeType)}
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
  onFillField: (fieldId: string, answer: string) => void;
  onFeedback: (rating: ResumeFeedbackRating) => void;
  onHide: () => void;
  onRestore: () => void;
  application: ApplicationRecord | null;
  outcome: OutcomeSignalResponse | null;
  trackingBusy: boolean;
  successReferenceCount: number | null;
  onRecordApplication: (resume: ResumeTailorResponse) => void;
  onRecordOutcome: (application: ApplicationRecord, outcomeType: SidePanelOutcomeType) => void;
}) {
  const { job } = props;
  const sponsorship = job.workflows.sponsorship.result;
  const resume = job.workflows.resume.result;
  const formAnswer = job.workflows.formAnswer.result;

  return (
    <article className="detail-card">
      <header className="detail-header">
        <div>
          <h2>{jobDisplayTitle(job.jobLead)}</h2>
          <small>{jobDisplaySubtitle(job.jobLead)}</small>
          <p>{job.jobLead.source_url}</p>
        </div>
        <span className="id-pill">{job.jobLead.id}</span>
      </header>
      <div className="action-row">
        {job.visibility === "hidden" ? (
          <button type="button" className="secondary-button" onClick={props.onRestore}>
            Restore Card
          </button>
        ) : (
          <button type="button" className="secondary-button" onClick={props.onHide}>
            Hide Card
          </button>
        )}
      </div>

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

      {resume ? (
        <ResumeResult
          result={resume}
          application={props.application}
          outcome={props.outcome}
          trackingBusy={props.trackingBusy}
          successReferenceCount={props.successReferenceCount}
          onFeedback={props.onFeedback}
          onRecordApplication={props.onRecordApplication}
          onRecordOutcome={props.onRecordOutcome}
        />
      ) : (
        <WorkflowMessage run={job.workflows.resume} />
      )}

      <div className="action-row">
        <button type="button" disabled={job.workflows.formAnswer.status === "running"} onClick={props.onDraftAnswer}>
          {job.workflows.formAnswer.status === "running" ? "Drafting..." : "Fill Form Answer"}
        </button>
      </div>

      {formAnswer ? (
        <FormAnswerResult result={formAnswer} onFillAnswer={props.onFillAnswer} onFillField={props.onFillField} />
      ) : (
        <WorkflowMessage run={job.workflows.formAnswer} />
      )}
    </article>
  );
}

function FormAnswerResult(props: {
  result: FormAnswerDraftResponse | FormAnswerDraftsResponse;
  onFillAnswer: (answer: string) => void;
  onFillField: (fieldId: string, answer: string) => void;
}) {
  if ("drafts" in props.result) {
    return (
      <section className="result-block">
        <strong>Answer Drafts</strong>
        <small>{props.result.ai_used ? "AI + fixed profile drafts" : "Fixed profile drafts"} · Requires review</small>
        {props.result.drafts.map((draft) => {
          const fieldId = draft.field_id;
          return (
            <article key={draft.id} className="draft-card">
              <span>{draft.question_text || draft.field_label || "Detected field"}</span>
              <small>
                {draft.intent || "custom"} · {draft.answer_type || "text"} · {Math.round((draft.confidence ?? 0) * 100)}%
              </small>
              <p>{draft.answer}</p>
              {draft.selected_option ? <small>Selected option: {draft.selected_option}</small> : null}
              {draft.evidence_summary.length > 0 ? <small>Evidence: {draft.evidence_summary.join(" ")}</small> : null}
              {draft.risk_flags.length > 0 ? <small>{draft.risk_flags.join(" ")}</small> : null}
              <button
                type="button"
                className="secondary-button"
                disabled={!fieldId}
                onClick={() => props.onFillField(fieldId, draft.answer)}
              >
                Fill This Field
              </button>
            </article>
          );
        })}
        {props.result.warnings.length > 0 ? <small>{props.result.warnings.join(" ")}</small> : null}
      </section>
    );
  }

  const singleResult = props.result as FormAnswerDraftResponse;
  return (
    <section className="result-block">
      <strong>Answer Draft</strong>
      <small>
        {singleResult.draft.question_text || singleResult.draft.field_label || "Detected field"} ·{" "}
        {singleResult.draft.intent || "custom"} · {Math.round((singleResult.draft.confidence ?? 0) * 100)}%
      </small>
      <p>{singleResult.draft.answer}</p>
      {singleResult.draft.selected_option ? <small>Selected option: {singleResult.draft.selected_option}</small> : null}
      {singleResult.draft.evidence_summary.length > 0 ? (
        <small>Evidence: {singleResult.draft.evidence_summary.join(" ")}</small>
      ) : null}
      <small>{singleResult.ai_used ? "AI draft" : "Fixed profile answer"} · Requires review</small>
      <button type="button" className="secondary-button" onClick={() => props.onFillAnswer(singleResult.draft.answer)}>
        Fill Current Field
      </button>
    </section>
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
  application: ApplicationRecord | null;
  outcome: OutcomeSignalResponse | null;
  trackingBusy: boolean;
  successReferenceCount: number | null;
  onFeedback: (rating: ResumeFeedbackRating) => void;
  onRecordApplication: (resume: ResumeTailorResponse) => void;
  onRecordOutcome: (application: ApplicationRecord, outcomeType: SidePanelOutcomeType) => void;
}) {
  const { result } = props;
  const docxUrl = getResumeArtifactUrl(result.resume_version.id, "docx");
  const markdownUrl = getResumeArtifactUrl(result.resume_version.id, "markdown");
  return (
    <section className="result-block">
      <strong>Tailored Resume</strong>
      <ArtifactEntry label="DOCX" url={docxUrl} localPath={result.docx_path || result.resume_version.file_path} />
      <ArtifactEntry label="Markdown" url={markdownUrl} localPath={result.markdown_path || "Not generated"} />
      <div className="compact-list">
        <span>Filename</span>
        <p>{result.filename_base || "Not available"}</p>
      </div>
      <small>
        {result.ai_used ? `AI: ${result.ai_provider_name || "provider"}` : "Local draft"} ·{" "}
        {result.cache.hit ? "Cache hit" : "Fresh result"} · {result.resume_version.change_summary}
      </small>
      <div className="compact-list">
        <span>Selected bullets</span>
        <p>{result.resume_version.selected_bullets.join(", ") || "None"}</p>
      </div>
      <div className="compact-list">
        <span>Success references</span>
        <p>{result.used_success_references.join(", ") || "None"}</p>
      </div>
      <div className="compact-list">
        <span>Layout budget</span>
        <p>{layoutBudgetText(result.layout_budget)}</p>
      </div>
      <div className="compact-list">
        <span>Quality checks</span>
        <p>{qualityCheckText(result.quality_checks)}</p>
      </div>
      {result.warnings.length > 0 ? (
        <ul>
          {result.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      <div className="feedback-grid">
        {FEEDBACK_ACTIONS.map((rating) => (
          <button key={rating} type="button" className="secondary-button" onClick={() => props.onFeedback(rating)}>
            {FEEDBACK_LABELS[rating]}
          </button>
        ))}
      </div>
      <ApplicationTracking
        resume={result}
        application={props.application}
        outcome={props.outcome}
        busy={props.trackingBusy}
        successReferenceCount={props.successReferenceCount}
        onRecordApplication={props.onRecordApplication}
        onRecordOutcome={props.onRecordOutcome}
      />
    </section>
  );
}

function ApplicationTracking(props: {
  resume: ResumeTailorResponse;
  application: ApplicationRecord | null;
  outcome: OutcomeSignalResponse | null;
  busy: boolean;
  successReferenceCount: number | null;
  onRecordApplication: (resume: ResumeTailorResponse) => void;
  onRecordOutcome: (application: ApplicationRecord, outcomeType: SidePanelOutcomeType) => void;
}) {
  return (
    <section className="tracking-block" aria-label="Application tracking">
      <div className="result-heading">
        <div>
          <strong>Application</strong>
          <span>{props.application ? props.application.status : "Not recorded"}</span>
        </div>
        {props.application ? <span className="id-pill">{props.application.id}</span> : null}
      </div>
      {props.application ? (
        <>
          <div className="compact-list">
            <span>Method</span>
            <p>{props.application.application_method}</p>
          </div>
          <div className="compact-list">
            <span>URL</span>
            <p>{props.application.application_url}</p>
          </div>
          <div className="feedback-grid">
            {OUTCOME_ACTIONS.map((outcomeType) => (
              <button
                key={outcomeType}
                type="button"
                className="secondary-button"
                disabled={props.busy}
                onClick={() => props.onRecordOutcome(props.application as ApplicationRecord, outcomeType)}
              >
                {OUTCOME_LABELS[outcomeType]}
              </button>
            ))}
          </div>
          {props.outcome ? (
            <small>
              Outcome id {props.outcome.outcome.id} · {OUTCOME_LABELS[props.outcome.outcome.outcome_type as SidePanelOutcomeType]}
              {props.outcome.success_reference.created ? ` · Success reference ${props.outcome.success_reference.id}` : ""}
              {props.successReferenceCount !== null ? ` · ${props.successReferenceCount} references total` : ""}
            </small>
          ) : (
            <small>Record replies or interview signals after they happen. NxJob does not submit forms.</small>
          )}
        </>
      ) : (
        <>
          <button type="button" disabled={props.busy} onClick={() => props.onRecordApplication(props.resume)}>
            {props.busy ? "Recording..." : "Record Application"}
          </button>
          <small>Use after you manually submit the application. No external page is clicked.</small>
        </>
      )}
    </section>
  );
}

function ArtifactEntry(props: { label: string; url: string; localPath: string }) {
  return (
    <div className="compact-list">
      <span>{props.label}</span>
      <p>
        <a href={props.url} target="_blank" rel="noreferrer">
          HTTP artifact
        </a>
        {" · "}
        <button type="button" className="text-button" onClick={() => copyText(props.url)}>
          Copy link
        </button>
      </p>
      <p>
        {props.localPath}
        {" · "}
        <button type="button" className="text-button" onClick={() => copyText(props.localPath)}>
          Copy path
        </button>
      </p>
    </div>
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
  if (!config || !config.master_resume_configured || !config.ai_provider_configured || !config.resume_output_dir_configured) {
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

function jobDisplayTitle(jobLead: JobLeadRecord): string {
  if (jobLead.job_title && jobLead.company_name) {
    return `${jobLead.job_title} | ${jobLead.company_name}`;
  }
  return jobLead.job_title || jobLead.page_title || "Untitled job";
}

function jobDisplaySubtitle(jobLead: JobLeadRecord): string {
  const parts: string[] = [jobLead.source_site];
  if (jobLead.location) parts.push(jobLead.location);
  return parts.join(" · ");
}

function visibleJobs(workspace: WorkspaceState): JobWorkspaceRecord[] {
  return workspace.jobs.filter((job) => (workspace.showHidden ? job.visibility === "hidden" : job.visibility !== "hidden"));
}

function normalizeUrlForPresence(url: string): string {
  try {
    const parsed = new URL(url);
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return url;
  }
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

function inferApplicationMethod(job: JobWorkspaceRecord): ApplicationMethod {
  if (job.jobLead.source_site === "company_ats") return "company_ats";
  return "manual";
}

function layoutBudgetText(layoutBudget: Record<string, unknown>): string {
  const body = layoutBudget.body_lines;
  const maxBody = layoutBudget.max_body_lines;
  const targetMin = layoutBudget.target_min_body_lines;
  if (typeof body === "number" && typeof maxBody === "number" && typeof targetMin === "number") {
    return `${body}/${maxBody} estimated body lines, target ${targetMin}-${maxBody}`;
  }

  if (typeof body === "number" && typeof maxBody === "number") {
    return `${body}/${maxBody} estimated body lines`;
  }
  return "Not available";
}

function qualityCheckText(qualityChecks: Record<string, unknown>): string {
  return [
    qualityStatus("one_page_budget_ok", "one-page budget", qualityChecks),
    qualityStatus("page_fill_target_met", "page fill", qualityChecks),
    qualityStatus("contact_line_single_line", "contact one line", qualityChecks),
    qualityStatus("education_years_present", "education years", qualityChecks),
    qualityStatus("experience_timeline_preserved", "experience timeline", qualityChecks)
  ].join(" · ");
}

function qualityStatus(key: string, label: string, qualityChecks: Record<string, unknown>): string {
  const value = qualityChecks[key];
  if (value === true) return `${label}: pass`;
  if (value === false) return `${label}: fail`;
  return `${label}: unknown`;
}

async function copyText(value: string) {
  if (!value || value === "Not generated") return;
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    // The visible link/path remains available when clipboard permission is unavailable.
  }
}
