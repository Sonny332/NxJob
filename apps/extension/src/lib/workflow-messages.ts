import type { JobLeadRecord, ResumeTailorResponse, SponsorshipAnalyzeResponse } from "./api-client";

export type RunSponsorshipMessage = {
  type: "NXJOB_RUN_SPONSORSHIP";
  jobLead: JobLeadRecord;
  forceRefresh: boolean;
  allowAi?: boolean;
};

export type RunTailorMessage = {
  type: "NXJOB_RUN_TAILOR";
  jobLead: JobLeadRecord;
  forceRefresh: boolean;
};

export type WorkflowMessage = RunSponsorshipMessage | RunTailorMessage;

export type WorkflowMessageResponse =
  | {
      ok: true;
      workflow: "sponsorship";
      result: SponsorshipAnalyzeResponse;
    }
  | {
      ok: true;
      workflow: "resume";
      result: ResumeTailorResponse;
    }
  | {
      ok: false;
      error: string;
    };

export function isWorkflowMessage(message: unknown): message is WorkflowMessage {
  if (!message || typeof message !== "object") return false;
  const candidate = message as { type?: unknown };
  return candidate.type === "NXJOB_RUN_SPONSORSHIP" || candidate.type === "NXJOB_RUN_TAILOR";
}
