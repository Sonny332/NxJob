import { browser } from "wxt/browser";

import type {
  FormAnswerDraftResponse,
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

export type JobWorkspaceRecord = {
  id: string;
  jobLead: JobLeadRecord;
  pageTitle: string;
  pageUrl: string;
  selectedTextLength: number;
  pageTextLength: number;
  createdAt: string;
  updatedAt: string;
  workflows: {
    sponsorship: WorkflowRun<SponsorshipAnalyzeResponse>;
    resume: WorkflowRun<ResumeTailorResponse>;
    formAnswer: WorkflowRun<FormAnswerDraftResponse>;
  };
};

export type WorkspaceState = {
  focusedJobId: string;
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
}): JobWorkspaceRecord {
  const now = new Date().toISOString();
  return {
    id: params.jobLead.id,
    jobLead: params.jobLead,
    pageTitle: params.pageTitle,
    pageUrl: params.pageUrl,
    selectedTextLength: params.selectedTextLength,
    pageTextLength: params.pageTextLength,
    createdAt: now,
    updatedAt: now,
    workflows: {
      sponsorship: emptyWorkflow(),
      resume: emptyWorkflow(),
      formAnswer: emptyWorkflow()
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
      jobs: state.jobs.slice(0, 20)
    }
  });
}

export function upsertWorkspaceJob(
  state: WorkspaceState,
  record: JobWorkspaceRecord
): WorkspaceState {
  const existing = state.jobs.find((job) => job.id === record.id || job.jobLead.jd_hash === record.jobLead.jd_hash);
  const nextRecord = existing
    ? {
        ...existing,
        jobLead: record.jobLead,
        pageTitle: record.pageTitle,
        pageUrl: record.pageUrl,
        selectedTextLength: record.selectedTextLength,
        pageTextLength: record.pageTextLength,
        updatedAt: new Date().toISOString()
      }
    : record;

  const jobs = [nextRecord, ...state.jobs.filter((job) => job.id !== existing?.id && job.id !== record.id)];
  return {
    focusedJobId: nextRecord.id,
    jobs
  };
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
    return { focusedJobId: "", jobs: [] };
  }

  const candidate = value as Partial<WorkspaceState>;
  return {
    focusedJobId: typeof candidate.focusedJobId === "string" ? candidate.focusedJobId : "",
    jobs: Array.isArray(candidate.jobs) ? candidate.jobs : []
  };
}
