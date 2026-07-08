import { browser } from "wxt/browser";

import type {
  FormAnswerDraftResponse,
  FormAnswerDraftsResponse,
  JobLeadRecord,
  ResumeTailorResponse,
  SponsorshipAnalyzeResponse
} from "./api-client";

const STORAGE_KEY = "nxjob.workspace.v1";

export type WorkflowStatus = "idle" | "running" | "completed" | "failed";

export type WorkflowRun<T> = {
  status: WorkflowStatus;
  updatedAt: string;
  traceId: string;
  result: T | null;
  error: string;
};

export type CaptureSummary = {
  isDuplicate: boolean;
  existingJobLeadId: string;
  dedupeAction: "" | "update_existing" | "create_new";
  requiresUserChoice: boolean;
  warnings: string[];
  jdSource: string;
  jdLength: number;
};

export type JobWorkspaceRecord = {
  id: string;
  jobLead: JobLeadRecord;
  pageTitle: string;
  pageUrl: string;
  selectedTextLength: number;
  pageTextLength: number;
  capture: CaptureSummary;
  createdAt: string;
  updatedAt: string;
  visibility: "active" | "hidden";
  hiddenAt: string;
  tabPresence: "open" | "closed" | "unknown";
  workflows: {
    sponsorship: WorkflowRun<SponsorshipAnalyzeResponse>;
    resume: WorkflowRun<ResumeTailorResponse>;
    formAnswer: WorkflowRun<FormAnswerDraftResponse | FormAnswerDraftsResponse>;
  };
};

export type WorkspaceState = {
  focusedJobId: string;
  showHidden: boolean;
  jobs: JobWorkspaceRecord[];
};

export function emptyWorkflow<T>(): WorkflowRun<T> {
  return {
    status: "idle",
    updatedAt: "",
    traceId: "",
    result: null,
    error: ""
  };
}

export function createWorkspaceRecord(params: {
  jobLead: JobLeadRecord;
  pageTitle: string;
  pageUrl: string;
  selectedTextLength: number;
  pageTextLength: number;
  capture: CaptureSummary;
}): JobWorkspaceRecord {
  const now = new Date().toISOString();
  return {
    id: params.jobLead.id,
    jobLead: params.jobLead,
    pageTitle: params.pageTitle,
    pageUrl: params.pageUrl,
    selectedTextLength: params.selectedTextLength,
    pageTextLength: params.pageTextLength,
    capture: params.capture,
    createdAt: now,
    updatedAt: now,
    visibility: "active",
    hiddenAt: "",
    tabPresence: "unknown",
    workflows: {
      sponsorship: emptyWorkflow<SponsorshipAnalyzeResponse>(),
      resume: emptyWorkflow<ResumeTailorResponse>(),
      formAnswer: emptyWorkflow<FormAnswerDraftResponse | FormAnswerDraftsResponse>()
    }
  };
}

export async function loadWorkspaceState(): Promise<WorkspaceState> {
  const stored = await browser.storage.local.get(STORAGE_KEY);
  return normalizeWorkspaceState(stored[STORAGE_KEY]);
}

export async function saveWorkspaceState(state: WorkspaceState): Promise<void> {
  await browser.storage.local.set({
    [STORAGE_KEY]: {
      focusedJobId: state.focusedJobId,
      showHidden: state.showHidden,
      jobs: state.jobs.slice(0, 20)
    }
  });
}

export function upsertWorkspaceJob(
  state: WorkspaceState,
  record: JobWorkspaceRecord
): WorkspaceState {
  const existing = state.jobs.find((job) => job.id === record.id || job.jobLead.jd_hash === record.jobLead.jd_hash);
  const clearsWorkflowResults =
    existing && record.capture.dedupeAction === "update_existing" && existing.jobLead.jd_hash !== record.jobLead.jd_hash;
  const nextRecord = existing
    ? {
        ...existing,
        jobLead: record.jobLead,
        pageTitle: record.pageTitle,
        pageUrl: record.pageUrl,
        selectedTextLength: record.selectedTextLength,
        pageTextLength: record.pageTextLength,
        capture: record.capture,
        updatedAt: new Date().toISOString(),
        visibility: "active" as const,
        hiddenAt: "",
        workflows: {
          sponsorship: clearsWorkflowResults
            ? emptyWorkflow<SponsorshipAnalyzeResponse>()
            : mergeWorkflowRun(
                existing.workflows.sponsorship,
                record.workflows.sponsorship,
                shouldKeepExistingSponsorshipResult,
                shouldUseIncomingSponsorshipResult
              ),
          resume: clearsWorkflowResults
            ? emptyWorkflow<ResumeTailorResponse>()
            : mergeWorkflowRun(existing.workflows.resume, record.workflows.resume),
          formAnswer: clearsWorkflowResults
            ? emptyWorkflow<FormAnswerDraftResponse | FormAnswerDraftsResponse>()
            : mergeWorkflowRun(existing.workflows.formAnswer, record.workflows.formAnswer)
        }
      }
    : record;

  const jobs = [nextRecord, ...state.jobs.filter((job) => job.id !== existing?.id && job.id !== record.id)];
  return {
    focusedJobId: nextRecord.id,
    showHidden: state.showHidden,
    jobs
  };
}

function mergeWorkflowRun<T>(
  existing: WorkflowRun<T>,
  incoming: WorkflowRun<T>,
  shouldKeepExistingResult?: (existingResult: T, incomingResult: T) => boolean,
  shouldUseIncomingResult?: (existingResult: T, incomingResult: T) => boolean
): WorkflowRun<T> {
  if (existing.result && incoming.result && shouldKeepExistingResult?.(existing.result, incoming.result)) return existing;
  if (existing.result && incoming.result && shouldUseIncomingResult?.(existing.result, incoming.result)) return incoming;
  if (existing.result && incoming.result) return newerWorkflowRun(existing, incoming);
  if (existing.result) return existing;
  if (incoming.result) return incoming;
  if (existing.status === "running") return existing;
  return incoming.status === "idle" ? existing : incoming;
}

function shouldKeepExistingSponsorshipResult(
  existing: SponsorshipAnalyzeResponse,
  incoming: SponsorshipAnalyzeResponse
): boolean {
  return existing.ai_used && !incoming.ai_used;
}

function shouldUseIncomingSponsorshipResult(
  existing: SponsorshipAnalyzeResponse,
  incoming: SponsorshipAnalyzeResponse
): boolean {
  return !existing.ai_used && incoming.ai_used;
}

function newerWorkflowRun<T>(existing: WorkflowRun<T>, incoming: WorkflowRun<T>): WorkflowRun<T> {
  const existingTime = Date.parse(existing.updatedAt);
  const incomingTime = Date.parse(incoming.updatedAt);
  if (!Number.isFinite(existingTime) || !Number.isFinite(incomingTime)) return existing;
  return incomingTime > existingTime ? incoming : existing;
}

export function updateWorkspaceJob(
  state: WorkspaceState,
  jobId: string,
  update: (job: JobWorkspaceRecord) => JobWorkspaceRecord
): WorkspaceState {
  return {
    ...state,
    jobs: state.jobs.map((job) => (job.id === jobId ? update(job) : job))
  };
}

function normalizeWorkspaceState(value: unknown): WorkspaceState {
  if (!value || typeof value !== "object") {
    return { focusedJobId: "", showHidden: false, jobs: [] };
  }

  const candidate = value as Partial<WorkspaceState>;
  return {
    focusedJobId: typeof candidate.focusedJobId === "string" ? candidate.focusedJobId : "",
    showHidden: typeof candidate.showHidden === "boolean" ? candidate.showHidden : false,
    jobs: Array.isArray(candidate.jobs) ? candidate.jobs.map(normalizeJobRecord) : []
  };
}

function normalizeJobRecord(job: JobWorkspaceRecord): JobWorkspaceRecord {
  return {
    ...job,
    capture: normalizeCaptureSummary(job.capture),
    visibility: job.visibility === "hidden" ? "hidden" : "active",
    hiddenAt: typeof job.hiddenAt === "string" ? job.hiddenAt : "",
    tabPresence: ["open", "closed", "unknown"].includes(job.tabPresence) ? job.tabPresence : "unknown"
  };
}

function normalizeCaptureSummary(capture: CaptureSummary | undefined): CaptureSummary {
  return {
    isDuplicate: Boolean(capture?.isDuplicate),
    existingJobLeadId: typeof capture?.existingJobLeadId === "string" ? capture.existingJobLeadId : "",
    dedupeAction:
      capture?.dedupeAction === "update_existing" || capture?.dedupeAction === "create_new" ? capture.dedupeAction : "",
    requiresUserChoice: Boolean(capture?.requiresUserChoice),
    warnings: Array.isArray(capture?.warnings) ? capture.warnings : [],
    jdSource: typeof capture?.jdSource === "string" ? capture.jdSource : "",
    jdLength: typeof capture?.jdLength === "number" ? capture.jdLength : 0
  };
}
