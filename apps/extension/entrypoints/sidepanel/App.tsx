import { type ChangeEvent, type Dispatch, type SetStateAction, useEffect, useMemo, useRef, useState } from "react";

import {
  activateAiProviderProfile,
  analyzeSponsorship,
  captureJobLead,
  checkConfigStatus,
  checkHealth,
  buildDolIndex,
  cleanupDolIndex,
  clearAiProvider,
  createApplication,
  createOutcome,
  deleteAiProviderProfile,
  getDolIndexJob,
  getDolIndexStatus,
  getResumeArtifactUrl,
  getWorkflowResults,
  listAiProviderProfiles,
  listApplications,
  listOutcomes,
  listSuccessReferences,
  saveAiProvider,
  saveMasterResume,
  saveResumeOutputDirectory,
  submitResumeFeedback,
  tailorResume,
  type ApplicationMethod,
  type ApplicationRecord,
  type AiProviderProfileRecord,
  type CaptureJobLeadResponse,
  type ConfigStatusResponse,
  type DolIndexBuildResponse,
  type DolIndexJob,
  type DolIndexStatus,
  type DolIndexStatusResponse,
  type JobLeadRecord,
  type OutcomeSignalResponse,
  type OutcomeType,
  type ResumeFeedbackRating,
  type ResumeTailorResponse,
  type SponsorshipAnalyzeResponse,
  type SponsorshipStatus
} from "../../src/lib/api-client";
import {
  captureFormFieldAnswer,
  captureActiveTabContext,
  listOpenTabUrls,
  scanActiveTabFormFields,
  type PageContext
} from "../../src/lib/page-capture";
import {
  clearSavedAnswers,
  copyAnswerAndTouch,
  deleteSavedAnswer,
  findAnswerCandidates,
  loadSavedAnswers,
  saveConfirmedAnswer,
  updateSavedAnswer,
  type AnswerCandidate,
  type SavedAnswer
} from "../../src/lib/form-answer-library";
import type { DetectedFormField } from "../../src/lib/form-context";
import {
  createWorkspaceRecord,
  emptyWorkflow,
  loadWorkspaceState,
  saveWorkspaceState,
  updateWorkspaceJob,
  upsertWorkspaceJob,
  type CaptureSummary,
  type JobWorkspaceRecord,
  type WorkspaceState
} from "../../src/lib/workspace-state";

type ServiceState = "checking" | "online" | "offline";
type WorkflowKey = "sponsorship" | "resume" | "formAnswer";
type TrackingStatus = "idle" | "running";
type DolIndexAction = "idle" | "building" | "cleaning";
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
    model: "gemini-3.1-flash-lite",
    help: "Use with a Gemini API key. Default is 3.1 Flash-Lite for non-grounded resume tailoring."
  },
  gemini_grounded: {
    label: "Gemini + Google Search",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    model: "gemini-3.5-flash",
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
const INITIAL_WORKSPACE_STATE: WorkspaceState = { focusedJobId: "", showHidden: false, jobs: [] };
type PendingDuplicateCapture = {
  context: PageContext;
  capture: CaptureJobLeadResponse;
};
type FormAnswerMatchRow = {
  field: DetectedFormField;
  candidates: AnswerCandidate[];
};
type PendingAnswerSave = {
  jobId: string;
  field: DetectedFormField;
  draftValue: string;
};

export function App() {
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [config, setConfig] = useState<ConfigStatusResponse | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceState>(INITIAL_WORKSPACE_STATE);
  const workspaceRef = useRef<WorkspaceState>(INITIAL_WORKSPACE_STATE);
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
  const [dolIndexAction, setDolIndexAction] = useState<DolIndexAction>("idle");
  const [pendingDuplicateCapture, setPendingDuplicateCapture] = useState<PendingDuplicateCapture | null>(null);
  const [formAnswerMatchesByJobId, setFormAnswerMatchesByJobId] = useState<Record<string, FormAnswerMatchRow[]>>({});
  const [savedAnswers, setSavedAnswers] = useState<SavedAnswer[]>([]);
  const [savedAnswerDrafts, setSavedAnswerDrafts] = useState<Record<string, string>>({});
  const [pendingAnswerSave, setPendingAnswerSave] = useState<PendingAnswerSave | null>(null);

  useEffect(() => {
    workspaceRef.current = workspace;
  }, [workspace]);

  useEffect(() => {
    let cancelled = false;

    loadWorkspaceState().then((state) => {
      if (!cancelled) {
        replaceWorkspaceState(state);
        void hydrateTrackingForJobs(state.jobs);
      }
    });
    void refreshSavedAnswers();
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

  useEffect(() => {
    if (settingsOpen && serviceState === "online") {
      void refreshDolIndexStatusFromSettings();
    }
  }, [settingsOpen, serviceState]);

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

  async function refreshSavedAnswers() {
    const records = await loadSavedAnswers();
    setSavedAnswers(records);
    setSavedAnswerDrafts(
      records.reduce<Record<string, string>>((drafts, entry) => {
        drafts[entry.id] = entry.answers.join("\n");
        return drafts;
      }, {})
    );
  }

  async function refreshFormAnswerMatches(jobId: string, fields: DetectedFormField[]) {
    const rows = await Promise.all(
      fields.map(async (field) => ({
        field,
        candidates: await findAnswerCandidates(field)
      }))
    );
    setFormAnswerMatchesByJobId((current) => ({
      ...current,
      [jobId]: rows
    }));
  }

  async function buildDolIndexFromSettings() {
    if (dolIndexAction !== "idle") return;

    setDolIndexAction("building");
    try {
      const job = await buildDolIndex();
      updateDolIndexJob(job);
      setMessage(job.message || "DOL index build started.");
      if (job.job_id) {
        await pollDolIndexJob(job.job_id);
      }
      const status = await getDolIndexStatus();
      updateDolIndexStatus(status);
      setMessage(dolIndexStatusMessage(status));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to build DOL index.");
      await refreshDolIndexStatusSilently();
    } finally {
      setDolIndexAction("idle");
    }
  }

  async function refreshDolIndexStatusSilently(): Promise<DolIndexStatusResponse | null> {
    try {
      const status = await getDolIndexStatus();
      updateDolIndexStatus(status);
      return status;
    } catch {
      return null;
    }
  }

  async function refreshDolIndexStatusFromSettings() {
    try {
      const status = await getDolIndexStatus();
      updateDolIndexStatus(status);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to refresh DOL index status.");
    }
  }

  async function cleanupDolIndexFromSettings() {
    if (dolIndexAction !== "idle") return;

    setDolIndexAction("cleaning");
    try {
      const cleanup = await cleanupDolIndex();
      const status = await getDolIndexStatus();
      updateDolIndexStatus(status);
      setMessage(`Cleaned ${cleanup.deleted_files.length} stale DOL cache files; freed ${formatBytes(cleanup.freed_bytes)}.${dolWarningSuffix(cleanup.warnings, " Warnings: ")}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to clean DOL cache.");
    } finally {
      setDolIndexAction("idle");
    }
  }

  async function pollDolIndexJob(jobId: string) {
    for (let attempt = 0; attempt < 720; attempt += 1) {
      await delay(Math.min(1000 + attempt * 500, 10000));
      const job = await getDolIndexJob(jobId);
      updateDolIndexJob(job);
      if (!isActiveDolJob(job)) {
        return;
      }
    }
    const status = await getDolIndexStatus();
    updateDolIndexStatus(status);
    setMessage("DOL index build is still running in the background. Settings will refresh its status when reopened.");
  }

  function updateDolIndexStatus(status: DolIndexStatusResponse) {
    setConfig((current) => (current ? { ...current, dol_index_status: status } : current));
  }

  function updateDolIndexJob(job: DolIndexBuildResponse | DolIndexJob) {
    setConfig((current) =>
      current
        ? {
            ...current,
            dol_index_status: {
              ...current.dol_index_status,
              current_job: job
            }
          }
        : current
    );
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

  async function finalizeCapturedJob(context: PageContext, capture: CaptureJobLeadResponse) {
    if (capture.dedupe.requires_user_choice) {
      setPendingDuplicateCapture({ context, capture });
      setMessage("Existing JobLead has linked records. Choose Update existing or Create new.");
      return;
    }

    setPendingDuplicateCapture(null);
    const nextRecord = createWorkspaceRecord({
      jobLead: capture.job_lead,
      pageTitle: context.title,
      pageUrl: context.url,
      selectedTextLength: context.selectedText.length,
      pageTextLength: context.captureText.length || context.pageTextExcerpt.length,
      capture: captureSummaryFromResponse(context, capture)
    });
    const hydratedRecord =
      capture.dedupe.action === "update_existing" ? nextRecord : await hydrateWorkflowResults(nextRecord);
    await hydrateTrackingForJobs([hydratedRecord]);

    const latestWorkspace = await loadWorkspaceState();
    const nextWorkspace = upsertWorkspaceJob(latestWorkspace, hydratedRecord);
    replaceWorkspaceState(nextWorkspace);
    await saveWorkspaceState(nextWorkspace);
    if (capture.dedupe.action === "update_existing") {
      setMessage("Existing JobLead updated. Running local sponsorship check...");
      await runSponsorship(
        {
          ...hydratedRecord,
          workflows: {
            sponsorship: emptyWorkflow(),
            resume: emptyWorkflow(),
            formAnswer: emptyWorkflow()
          }
        },
        { forceRefresh: true, allowAi: false }
      );
      return;
    }
    const sponsorshipResult = hydratedRecord.workflows.sponsorship.result;
    if (!sponsorshipResult) {
      setMessage("Current job captured. Running local sponsorship check...");
      await runSponsorship(hydratedRecord, { allowAi: false });
      return;
    }
    if (!sponsorshipResult.ai_used) {
      setMessage("Current job captured. Refreshing local sponsorship check...");
      await runSponsorship(hydratedRecord, { forceRefresh: true, allowAi: false });
      return;
    }
    setMessage(capture.dedupe.is_duplicate ? "Duplicate JD captured." : "Current job captured.");
  }

  async function captureCurrentJob() {
    try {
      setMessage("Capturing current tab...");
      const context = await captureActiveTabContext();
      setPageContext(context);
      const capture = await captureJobLead(context, { duplicateAction: "" });
      await finalizeCapturedJob(context, capture);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to capture current job.");
    }
  }

  async function resolvePendingDuplicate(action: "update_existing" | "create_new") {
    if (!pendingDuplicateCapture) return;

    try {
      setMessage("Resolving duplicate capture...");
      const { context } = pendingDuplicateCapture;
      const capture = await captureJobLead(context, { duplicateAction: action });
      await finalizeCapturedJob(context, capture);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to resolve duplicate capture.");
    }
  }

  async function runSponsorship(
    job: JobWorkspaceRecord,
    options: { forceRefresh?: boolean; allowAi?: boolean } = {}
  ) {
    if (job.workflows.sponsorship.status === "running") {
      setMessage("Sponsorship analysis is already running for this job.");
      return;
    }

    const allowAi = options.allowAi ?? true;
    markWorkflow(job.id, "sponsorship", "running");
    try {
      const result = await analyzeSponsorship(job.jobLead, null, {
        forceRefresh: options.forceRefresh ?? false,
        allowAi
      });
      const savedResult = setWorkflowResult(job.id, "sponsorship", result);
      if (!allowAi) {
        if (savedResult.ai_used) {
          setMessage("Existing AI sponsorship result kept.");
          return;
        }
        setMessage(savedResult.cache.hit ? "Local sponsorship result restored from cache." : "Local sponsorship check completed.");
        return;
      }
      setMessage(savedResult.cache.hit ? "Sponsorship result restored from cache." : "Sponsorship analysis completed.");
    } catch (error) {
      setWorkflowError(job.id, "sponsorship", error);
      if (!allowAi) {
        setMessage(error instanceof Error ? `Local sponsorship check failed: ${error.message}` : "Local sponsorship check failed.");
      }
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
      const result = await tailorResume(job.jobLead, {
        forceRefresh
      });
      const savedResult = setWorkflowResult(job.id, "resume", result);
      setMessage(savedResult.cache.hit ? "Tailored resume restored from cache." : "Tailored resume generated.");
    } catch (error) {
      setWorkflowError(job.id, "resume", error);
    }
  }

  async function runFormAnswer(job: JobWorkspaceRecord) {
    markWorkflow(job.id, "formAnswer", "running");
    try {
      const fields = await scanActiveTabFormFields();
      await refreshFormAnswerMatches(job.id, fields);
      finishWorkflowWithoutResult(job.id, "formAnswer");
      setMessage(
        fields.length > 0
          ? `Found ${fields.length} form questions. Saved answers are matched locally.`
          : "No supported form questions were detected on this page."
      );
    } catch (error) {
      setWorkflowError(job.id, "formAnswer", error);
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

  async function copySavedAnswer(jobId: string, answerId: string, value: string) {
    try {
      await copyAnswerAndTouch(answerId, value, writeFormAnswerToClipboard);
      const fields = (formAnswerMatchesByJobId[jobId] ?? []).map((row) => row.field);
      await refreshSavedAnswers();
      await refreshFormAnswerMatches(jobId, fields);
      setMessage("Answer copied.");
    } catch (error) {
      setMessage(error instanceof Error ? `Could not copy answer: ${error.message}` : "Could not copy answer.");
    }
  }

  async function startSaveAnswer(jobId: string, field: DetectedFormField) {
    try {
      const captured = await captureFormFieldAnswer(field.fieldId);
      const draftValue = captured.answers.join("\n").trim();
      if (!draftValue) {
        setMessage("This field is empty. Fill it on the page first, then save the answer.");
        return;
      }
      setPendingAnswerSave({ jobId, field, draftValue });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to capture the current field answer.");
    }
  }

  async function confirmSaveAnswer() {
    if (!pendingAnswerSave) return;
    const answers = pendingAnswerSave.draftValue
      .split(/\r?\n/)
      .map((value) => value.trim())
      .filter(Boolean);
    if (answers.length === 0) {
      setMessage("Answer cannot be empty.");
      return;
    }

    await saveConfirmedAnswer({
      question: pendingAnswerSave.field.questionText,
      fieldType: pendingAnswerSave.field.inputType,
      answers,
      sensitive: isSensitiveField(pendingAnswerSave.field)
    });
    const fields = (formAnswerMatchesByJobId[pendingAnswerSave.jobId] ?? []).map((row) => row.field);
    setPendingAnswerSave(null);
    await refreshSavedAnswers();
    await refreshFormAnswerMatches(pendingAnswerSave.jobId, fields);
    setMessage("Saved in this browser profile.");
  }

  async function saveEditedAnswer(answerId: string) {
    const draft = savedAnswerDrafts[answerId] ?? "";
    const answers = draft
      .split(/\r?\n/)
      .map((value) => value.trim())
      .filter(Boolean);
    if (answers.length === 0) {
      setMessage("Answer cannot be empty.");
      return;
    }
    await updateSavedAnswer(answerId, answers);
    await refreshSavedAnswers();
    setMessage("Saved answer updated.");
  }

  async function removeSavedAnswer(answerId: string) {
    await deleteSavedAnswer(answerId);
    await refreshSavedAnswers();
    setMessage("Saved answer removed.");
  }

  async function clearAllSavedAnswers() {
    if (!window.confirm("Clear all saved answers from this browser profile?")) return;
    await clearSavedAnswers();
    await refreshSavedAnswers();
    setMessage("Saved answers cleared.");
  }

  function hideJob(jobId: string) {
    updateWorkspaceState((current) => {
      const updated = updateWorkspaceJob(current, jobId, (job) => ({
        ...job,
        visibility: "hidden",
        hiddenAt: new Date().toISOString()
      }));
      return updated.focusedJobId === jobId ? { ...updated, focusedJobId: visibleJobs(updated)[0]?.id ?? "" } : updated;
    });
  }

  function restoreJob(jobId: string) {
    updateWorkspaceState((current) =>
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
      updateWorkspaceState((current) => ({
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
    updateWorkspaceState((current) =>
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

  function finishWorkflowWithoutResult(jobId: string, key: WorkflowKey) {
    updateWorkspaceState((current) =>
      updateWorkspaceJob(current, jobId, (job) => ({
        ...job,
        updatedAt: new Date().toISOString(),
        workflows: {
          ...job.workflows,
          [key]: {
            status: "completed",
            updatedAt: new Date().toISOString(),
            traceId: "",
            result: null,
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
  ): SponsorshipAnalyzeResponse;
  function setWorkflowResult(jobId: string, key: "resume", result: ResumeTailorResponse): ResumeTailorResponse;
  function setWorkflowResult(
    jobId: string,
    key: WorkflowKey,
    result: SponsorshipAnalyzeResponse | ResumeTailorResponse
  ) {
    const currentJob = workspaceRef.current.jobs.find((job) => job.id === jobId) ?? null;
    const resultToSave =
      key === "sponsorship"
        ? resolveSponsorshipResultToSave(
            currentJob?.workflows.sponsorship.result ?? null,
            result as SponsorshipAnalyzeResponse
          )
        : result;

    updateWorkspaceState((current) =>
      updateWorkspaceJob(current, jobId, (job) => ({
          ...job,
          updatedAt: new Date().toISOString(),
          workflows: {
            ...job.workflows,
            [key]: {
              status: "completed",
              updatedAt: new Date().toISOString(),
              traceId: resultToSave.trace_id,
              result: resultToSave,
              error: ""
            }
          }
        }))
    );
    return resultToSave;
  }

  function setWorkflowError(jobId: string, key: WorkflowKey, error: unknown) {
    const messageText = error instanceof Error ? error.message : "Workflow failed.";
    updateWorkspaceState((current) =>
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

  function replaceWorkspaceState(nextState: WorkspaceState): WorkspaceState {
    workspaceRef.current = nextState;
    setWorkspace(nextState);
    return nextState;
  }

  function updateWorkspaceState(update: (current: WorkspaceState) => WorkspaceState): WorkspaceState {
    return replaceWorkspaceState(update(workspaceRef.current));
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
                <option value="minimal">Minimal</option>
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
            {config?.dol_index_status ? (
              <DolIndexSettings
                status={config.dol_index_status}
                action={dolIndexAction}
                onBuild={buildDolIndexFromSettings}
                onCleanup={cleanupDolIndexFromSettings}
              />
            ) : null}
            <div className="profile-list">
              <div className="section-heading">
                <strong>Saved Answers</strong>
                <button type="button" className="text-button" onClick={clearAllSavedAnswers} disabled={savedAnswers.length === 0}>
                  Clear All
                </button>
              </div>
              {savedAnswers.length > 0 ? (
                savedAnswers.map((answer) => (
                  <div key={answer.id} className="profile-row saved-answer-row">
                    <textarea
                      value={savedAnswerDrafts[answer.id] ?? ""}
                      onChange={(event) =>
                        setSavedAnswerDrafts((current) => ({
                          ...current,
                          [answer.id]: event.target.value
                        }))
                      }
                    />
                    <div className="inline-actions">
                      <button type="button" className="secondary-button" onClick={() => saveEditedAnswer(answer.id)}>
                        Save
                      </button>
                      <button type="button" className="secondary-button" onClick={() => removeSavedAnswer(answer.id)}>
                        Delete
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <small>No saved answers yet.</small>
              )}
            </div>
            <small>
              NxJob uses local private config first. Environment variables are only a development fallback. Keys and resume contents are not written to logs.
            </small>
          </div>
        ) : null}
      </section>

      <section className="capture-strip" aria-label="Capture">
        <button type="button" onClick={() => void captureCurrentJob()}>
          Capture Current Tab
        </button>
        <div>
          <strong>{pageContext?.title ?? "No active capture yet."}</strong>
          <small>{pageContext ? `${pageContext.selectedText.length} selected chars` : "Select a JD, then capture."}</small>
        </div>
      </section>

      {pendingDuplicateCapture ? (
        <CaptureResultCard
          capture={captureSummaryFromResponse(pendingDuplicateCapture.context, pendingDuplicateCapture.capture)}
          dolWarnings={[]}
          pendingChoice
          onUpdateExisting={() => void resolvePendingDuplicate("update_existing")}
          onCreateNew={() => void resolvePendingDuplicate("create_new")}
        />
      ) : focusedJob ? (
        <CaptureResultCard
          capture={focusedJob.capture}
          dolWarnings={captureDolWarnings(focusedJob)}
          pendingChoice={false}
        />
      ) : null}

      <section className="workspace" aria-label="Job workspace">
        <nav className="job-list" aria-label="Captured jobs">
          <div className="job-list-tools">
            <button type="button" className="secondary-button" onClick={refreshOpenTabs}>
              Refresh Tabs
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => updateWorkspaceState((current) => ({ ...current, showHidden: !current.showHidden }))}
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
              onClick={() => updateWorkspaceState((current) => ({ ...current, focusedJobId: job.id }))}
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
              onAnalyze={() => runSponsorship(focusedJob, { allowAi: true })}
              onAnalyzeRefresh={() => runSponsorship(focusedJob, { forceRefresh: true, allowAi: false })}
              onTailor={() => runTailor(focusedJob)}
              onTailorRefresh={() => runTailor(focusedJob, true)}
              onDraftAnswer={() => runFormAnswer(focusedJob)}
              formAnswerMatches={formAnswerMatchesByJobId[focusedJob.id] ?? []}
              onCopyAnswer={(answerId, value) => copySavedAnswer(focusedJob.id, answerId, value)}
              onSaveAnswer={(field) => startSaveAnswer(focusedJob.id, field)}
              pendingAnswerSave={pendingAnswerSave}
              onPendingAnswerSaveChange={setPendingAnswerSave}
              onConfirmSaveAnswer={confirmSaveAnswer}
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

function DolIndexSettings(props: {
  status: DolIndexStatus;
  action: DolIndexAction;
  onBuild: () => void;
  onCleanup: () => void;
}) {
  const currentJob = props.status.current_job;
  const jobActive = Boolean(currentJob && isActiveDolJob(currentJob));
  const busy = props.action !== "idle";
  const disabled = busy || jobActive;

  return (
    <section className="result-block" aria-label="DOL Index">
      <div className="result-heading">
        <div>
          <strong>DOL Index</strong>
          <span>{humanizeDolStatus(props.status.status)}</span>
        </div>
        <span className={props.status.active_index_ready ? "setup-ok" : "setup-needed"}>
          {props.status.active_index_ready ? "ready" : "not ready"}
        </span>
      </div>
      <div className="compact-list">
        <span>Cache dir</span>
        <p>{props.status.cache_dir || "Not configured"}</p>
      </div>
      <div className="compact-list">
        <span>Cache size</span>
        <p>
          {formatBytes(props.status.cache_size_bytes)} / {formatBytes(props.status.max_cache_bytes)}
        </p>
      </div>
      <div className="compact-list">
        <span>Last built</span>
        <p>{formatDateTime(props.status.last_built_at)} · {props.status.row_count.toLocaleString()} rows</p>
      </div>
      <div className="compact-list">
        <span>Selected FY files</span>
        <p>{props.status.selected_files.map(selectedDolFileLabel).join(", ") || "None"}</p>
      </div>
      {props.status.warnings.length > 0 ? (
        <div className="questions">
          <strong>Warnings</strong>
          <ul>
            {props.status.warnings.map((warning) => (
              <li key={warning}>{humanizeDolMessage(warning)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {currentJob ? (
        <div className="compact-list">
          <span>Current job</span>
          <p>
            {currentJob.status || "unknown"} · {currentJob.phase || "phase unknown"} · {currentJob.message || currentJob.error || currentJob.job_id}
            {currentJob.progress_total > 0 ? ` · ${currentJob.progress_current}/${currentJob.progress_total}` : ""}
          </p>
        </div>
      ) : null}
      <div className="feedback-grid">
        <button type="button" className="secondary-button" disabled={disabled} onClick={props.onBuild}>
          {props.action === "building" || jobActive ? "Building..." : "Build / Refresh"}
        </button>
        <button type="button" className="secondary-button" disabled={disabled} onClick={props.onCleanup}>
          {props.action === "cleaning" ? "Cleaning..." : "Clean stale cache"}
        </button>
      </div>
      <small>DOL history lookup runs locally from the cache. Capture, sponsorship analysis, and resume work remain available while this job runs.</small>
    </section>
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
  formAnswerMatches: FormAnswerMatchRow[];
  onCopyAnswer: (answerId: string, value: string) => void;
  onSaveAnswer: (field: DetectedFormField) => void;
  pendingAnswerSave: PendingAnswerSave | null;
  onPendingAnswerSaveChange: Dispatch<SetStateAction<PendingAnswerSave | null>>;
  onConfirmSaveAnswer: () => void;
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
  const canRunAiSponsorship = canRunAiSponsorshipReview(sponsorship);

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
        <button
          type="button"
          disabled={job.workflows.sponsorship.status === "running" || !canRunAiSponsorship}
          onClick={props.onAnalyze}
        >
          {job.workflows.sponsorship.status === "running" ? "Analyzing..." : "Analyze Sponsorship"}
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={job.workflows.sponsorship.status === "running" || Boolean(sponsorship?.ai_used)}
          onClick={props.onAnalyzeRefresh}
        >
          Re-run Local
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
          {job.workflows.formAnswer.status === "running" ? "Scanning..." : "Find Form Answers"}
        </button>
      </div>

      {props.formAnswerMatches.length > 0 ? (
        <FormAnswerResult
          jobId={job.id}
          rows={props.formAnswerMatches}
          onCopyAnswer={props.onCopyAnswer}
          onSaveAnswer={props.onSaveAnswer}
          pendingAnswerSave={props.pendingAnswerSave}
          onPendingAnswerSaveChange={props.onPendingAnswerSaveChange}
          onConfirmSaveAnswer={props.onConfirmSaveAnswer}
        />
      ) : job.workflows.formAnswer.status === "completed" ? (
        <section className="result-block">
          <strong>Form Answers</strong>
          <small>No supported form questions were detected.</small>
        </section>
      ) : (
        <WorkflowMessage run={job.workflows.formAnswer} />
      )}
    </article>
  );
}

function CaptureResultCard(props: {
  capture: CaptureSummary;
  dolWarnings: string[];
  pendingChoice: boolean;
  onUpdateExisting?: () => void;
  onCreateNew?: () => void;
}) {
  return (
    <section className="result-block" aria-label="Capture result">
      <div className="result-heading">
        <div>
          <strong>Capture Result</strong>
          <span>{props.capture.isDuplicate ? "Duplicate" : "New JobLead"}</span>
        </div>
        <span className={props.capture.isDuplicate ? "setup-needed" : "setup-ok"}>
          {props.capture.isDuplicate ? "duplicate" : "new"}
        </span>
      </div>
      <div className="compact-list">
        <span>JD source</span>
        <p>{humanizeCaptureSource(props.capture.jdSource)}</p>
      </div>
      <div className="compact-list">
        <span>JD length</span>
        <p>{props.capture.jdLength} chars</p>
      </div>
      {props.dolWarnings.length > 0 ? (
        <div className="questions">
          <strong>DOL warning</strong>
          <ul>
            {props.dolWarnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {props.capture.warnings.length > 0 ? (
        <div className="questions">
          <strong>Warnings</strong>
          <ul>
            {props.capture.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {props.pendingChoice ? (
        <div className="feedback-grid">
          <button type="button" onClick={props.onUpdateExisting}>
            Update existing
          </button>
          <button type="button" className="secondary-button" onClick={props.onCreateNew}>
            Create new
          </button>
        </div>
      ) : null}
    </section>
  );
}

function FormAnswerResult(props: {
  jobId: string;
  rows: FormAnswerMatchRow[];
  onCopyAnswer: (answerId: string, value: string) => void;
  onSaveAnswer: (field: DetectedFormField) => void;
  pendingAnswerSave: PendingAnswerSave | null;
  onPendingAnswerSaveChange: Dispatch<SetStateAction<PendingAnswerSave | null>>;
  onConfirmSaveAnswer: () => void;
}) {
  return (
    <section className="result-block">
      <strong>Form Answers</strong>
      <small>Detected locally. Copy or save only.</small>
      <div className="draft-list">
        {props.rows.map((row) => (
          <article key={row.field.fieldId} className="draft-card">
            <span>{row.field.questionText || "Choose manually"}</span>
            {row.candidates.length > 0 ? (
              row.candidates.map((candidate) => (
                <div key={candidate.answer.id} className="answer-row">
                  <div>
                    <p>{candidate.answer.answers.join(" / ")}</p>
                    <small>{candidate.confidenceLabel}</small>
                  </div>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => props.onCopyAnswer(candidate.answer.id, candidate.answer.answers.join("\n"))}
                  >
                    Copy
                  </button>
                </div>
              ))
            ) : (
              <small>{row.field.inputType === "custom_select" && !row.field.questionText ? "Choose manually" : "No saved answer"}</small>
            )}
            {!(row.field.inputType === "custom_select" && !row.field.questionText) ? (
              <button type="button" className="secondary-button" onClick={() => props.onSaveAnswer(row.field)}>
                Save this answer
              </button>
            ) : null}
            {props.pendingAnswerSave?.jobId === props.jobId && props.pendingAnswerSave.field.fieldId === row.field.fieldId ? (
              <div className="answer-save-confirmation" aria-label="Save answer confirmation">
                <div className="result-heading">
                  <div>
                    <strong>Save This Answer</strong>
                    <span>{props.pendingAnswerSave.field.inputType}</span>
                  </div>
                </div>
                <div className="compact-list">
                  <span>Question</span>
                  <p>{props.pendingAnswerSave.field.questionText}</p>
                </div>
                <label>
                  <span>Answer</span>
                  <textarea
                    value={props.pendingAnswerSave.draftValue}
                    onChange={(event) =>
                      props.onPendingAnswerSaveChange((current) =>
                        current ? { ...current, draftValue: event.target.value } : current
                      )
                    }
                  />
                </label>
                <small>Only saved in this browser profile.</small>
                <div className="inline-actions">
                  <button type="button" onClick={props.onConfirmSaveAnswer}>
                    Confirm Save
                  </button>
                  <button type="button" className="secondary-button" onClick={() => props.onPendingAnswerSaveChange(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function SponsorshipResult({ result }: { result: SponsorshipAnalyzeResponse }) {
  const hasDolHistory = result.evidence.some((item) => item.source === "dol_lca_history");

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
        {result.ai_used ? "AI fallback" : "Local rule"} · {hasDolHistory ? "DOL history" : "JD evidence"} ·{" "}
        {result.cache.hit ? "Cache hit" : "Fresh result"} · Not a legal conclusion
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
      {result.sponsorship.risk_flags.length > 0 ? (
        <div className="questions">
          <strong>Notes</strong>
          <ul>
            {result.sponsorship.risk_flags.map((flag) => (
              <li key={flag}>{humanizeSponsorshipNote(flag)}</li>
            ))}
          </ul>
        </div>
      ) : null}
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

function captureSummaryFromResponse(context: PageContext, capture: CaptureJobLeadResponse): CaptureSummary {
  return {
    isDuplicate: capture.dedupe.is_duplicate,
    existingJobLeadId: capture.dedupe.existing_job_lead_id ?? "",
    dedupeAction: capture.dedupe.action,
    requiresUserChoice: capture.dedupe.requires_user_choice,
    warnings: capture.dedupe.warnings,
    jdSource: context.captureSource,
    jdLength: context.captureText.length || context.pageTextExcerpt.length
  };
}

function captureDolWarnings(job: JobWorkspaceRecord): string[] {
  const result = job.workflows.sponsorship.result;
  if (!result) return [];
  const warnings = [
    ...result.sponsorship.risk_flags.filter((flag) => flag.startsWith("dol_lca_") || flag === "cache_expired_network_failed"),
    ...result.evidence
      .filter((item) => item.source === "dol_lca_history" && item.evidence_text.toLowerCase().includes("warning"))
      .map((item) => item.evidence_text)
  ];
  return Array.from(new Set(warnings.map(humanizeSponsorshipNote)));
}

function humanizeCaptureSource(source: string): string {
  const labels: Record<string, string> = {
    selected_text: "Selected text",
    linkedin_job_detail: "LinkedIn auto capture",
    page_text_excerpt: "Page excerpt"
  };
  return labels[source] ?? (source || "Unknown");
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

function isAmbiguousSponsorshipStatus(status: SponsorshipStatus): boolean {
  return status === "needs_confirmation" || status === "unknown";
}

function canRunAiSponsorshipReview(result: SponsorshipAnalyzeResponse | null): boolean {
  return !result || isAmbiguousSponsorshipStatus(result.sponsorship.status) || isDolOnlyLikelySupport(result);
}

function isDolOnlyLikelySupport(result: SponsorshipAnalyzeResponse): boolean {
  return (
    result.sponsorship.status === "likely_supports" &&
    !result.ai_used &&
    result.evidence.some((item) => item.source === "dol_lca_history")
  );
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

async function writeFormAnswerToClipboard(value: string): Promise<void> {
  if (!value.trim()) {
    throw new Error("There is no answer to copy.");
  }
  await navigator.clipboard.writeText(value);
}

function isActiveDolJob(job: DolIndexJob): boolean {
  return job.status === "queued" || job.status === "running";
}

function dolIndexStatusMessage(status: DolIndexStatus): string {
  return `DOL index ${humanizeDolStatus(status.status)}: ${status.row_count.toLocaleString()} rows.${dolWarningSuffix(status.warnings, " ")}`;
}

function humanizeDolStatus(status: string): string {
  const labels: Record<string, string> = {
    ready: "Ready",
    not_built: "Not built",
    refresh_required: "Refresh required",
    expired: "Expired",
    failed_verification: "Failed verification",
    building: "Building"
  };
  return labels[status] ?? status.replace(/_/g, " ");
}

function humanizeSponsorshipNote(note: string): string {
  if (note.startsWith("dol_lca_") || note === "cache_expired_network_failed") {
    return humanizeDolMessage(note);
  }
  return note;
}

function dolWarningSuffix(warnings: string[], prefix: string): string {
  return warnings.length > 0 ? `${prefix}${warnings.map(humanizeDolMessage).join(" ")}` : "";
}

function humanizeDolMessage(warning: string): string {
  const labels: Record<string, string> = {
    dol_lca_index_not_ready: "DOL index is not ready. Build it in Settings to enable employer history lookup.",
    dol_lca_index_building: "DOL index is currently building. Employer history lookup will be available when it finishes.",
    dol_lca_index_refresh_required: "DOL index has newer source files available. Refresh it in Settings.",
    dol_lca_index_expired: "DOL index is expired. Refresh it in Settings before relying on employer history.",
    dol_lca_index_failed_verification: "DOL index failed verification. Rebuild it in Settings.",
    cache_expired_network_failed: "DOL cache is expired and the network refresh failed. Refresh it in Settings when the network is available."
  };
  if (warning.startsWith("skip_outside_cache:")) {
    return "Skipped a file outside the configured DOL cache directory.";
  }
  return labels[warning] ?? warning.replace(/_/g, " ");
}

function selectedDolFileLabel(file: DolIndexStatus["selected_files"][number]): string {
  const quarter = file.quarter ? ` Q${file.quarter}` : "";
  const size = file.size_bytes > 0 ? ` (${formatBytes(file.size_bytes)})` : "";
  return `FY${file.fy}${quarter}${size}`;
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  const digits = unitIndex === 0 || size >= 10 ? 0 : 1;
  return `${size.toFixed(digits)} ${units[unitIndex]}`;
}

function formatDateTime(value: string): string {
  if (!value) return "Never";
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  return new Date(timestamp).toLocaleString();
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function resolveSponsorshipResultToSave(
  existingResult: SponsorshipAnalyzeResponse | null,
  incomingResult: SponsorshipAnalyzeResponse
): SponsorshipAnalyzeResponse {
  if (!incomingResult.ai_used && existingResult?.ai_used) {
    return existingResult;
  }
  return incomingResult;
}
