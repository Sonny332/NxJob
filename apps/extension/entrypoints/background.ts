import { analyzeSponsorship, tailorResume } from "../src/lib/api-client";
import {
  loadWorkspaceState,
  saveWorkspaceState,
  updateWorkspaceJob
} from "../src/lib/workspace-state";
import {
  isWorkflowMessage,
  type RunSponsorshipMessage,
  type RunTailorMessage,
  type WorkflowMessageResponse
} from "../src/lib/workflow-messages";

const running = new Map<string, Promise<WorkflowMessageResponse>>();

export default defineBackground(() => {
  if (chrome.sidePanel?.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {
      // The popup remains the explicit launcher when side panel behavior is unavailable.
    });
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!isWorkflowMessage(message)) return false;

    const key = workflowRunKey(message);
    let task = running.get(key);
    if (!task) {
      task = runWorkflow(message).finally(() => {
        running.delete(key);
      });
      running.set(key, task);
    }

    task.then(sendResponse);
    return true;
  });
});

function workflowRunKey(message: RunSponsorshipMessage | RunTailorMessage): string {
  const workflow = message.type === "NXJOB_RUN_SPONSORSHIP" ? "sponsorship" : "resume";
  return `${workflow}:${message.jobLead.id}:${message.jobLead.jd_hash}:${message.forceRefresh ? "refresh" : "cached"}`;
}

async function runWorkflow(message: RunSponsorshipMessage | RunTailorMessage): Promise<WorkflowMessageResponse> {
  if (message.type === "NXJOB_RUN_SPONSORSHIP") {
    await setWorkflowStatus(message.jobLead.id, "sponsorship", "running", "");
    try {
      const result = await analyzeSponsorship(message.jobLead, null, {
        forceRefresh: message.forceRefresh
      });
      await setWorkflowResult(message.jobLead.id, "sponsorship", result);
      return { ok: true, workflow: "sponsorship", result };
    } catch (error) {
      const messageText = error instanceof Error ? error.message : "Sponsorship analysis failed.";
      await setWorkflowStatus(message.jobLead.id, "sponsorship", "failed", messageText);
      return { ok: false, error: messageText };
    }
  }

  await setWorkflowStatus(message.jobLead.id, "resume", "running", "");
  try {
    const result = await tailorResume(message.jobLead, {
      forceRefresh: message.forceRefresh
    });
    await setWorkflowResult(message.jobLead.id, "resume", result);
    return { ok: true, workflow: "resume", result };
  } catch (error) {
    const messageText = error instanceof Error ? error.message : "Resume tailor failed.";
    await setWorkflowStatus(message.jobLead.id, "resume", "failed", messageText);
    return { ok: false, error: messageText };
  }
}

async function setWorkflowStatus(
  jobId: string,
  workflow: "sponsorship" | "resume",
  status: "running" | "failed",
  error: string
) {
  const state = await loadWorkspaceState();
  await saveWorkspaceState(
    updateWorkspaceJob(state, jobId, (job) => ({
      ...job,
      updatedAt: new Date().toISOString(),
      workflows: {
        ...job.workflows,
        [workflow]: {
          ...job.workflows[workflow],
          status,
          updatedAt: new Date().toISOString(),
          error
        }
      }
    }))
  );
}

async function setWorkflowResult(
  jobId: string,
  workflow: "sponsorship",
  result: Awaited<ReturnType<typeof analyzeSponsorship>>
): Promise<void>;
async function setWorkflowResult(
  jobId: string,
  workflow: "resume",
  result: Awaited<ReturnType<typeof tailorResume>>
): Promise<void>;
async function setWorkflowResult(
  jobId: string,
  workflow: "sponsorship" | "resume",
  result: Awaited<ReturnType<typeof analyzeSponsorship>> | Awaited<ReturnType<typeof tailorResume>>
) {
  const state = await loadWorkspaceState();
  await saveWorkspaceState(
    updateWorkspaceJob(state, jobId, (job) => ({
      ...job,
      updatedAt: new Date().toISOString(),
      workflows: {
        ...job.workflows,
        [workflow]: {
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
