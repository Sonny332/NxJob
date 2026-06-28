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
  const cacheMode = message.forceRefresh ? "refresh" : "cached";
  const aiMode = message.type === "NXJOB_RUN_SPONSORSHIP" && message.allowAi === false ? "local" : "ai";
  return `${workflow}:${message.jobLead.id}:${message.jobLead.jd_hash}:${cacheMode}:${aiMode}`;
}

async function runWorkflow(message: RunSponsorshipMessage | RunTailorMessage): Promise<WorkflowMessageResponse> {
  if (message.type === "NXJOB_RUN_SPONSORSHIP") {
    await setWorkflowStatus(message.jobLead.id, "sponsorship", "running", "");
    try {
      const result = await analyzeSponsorship(message.jobLead, null, {
        forceRefresh: message.forceRefresh,
        allowAi: message.allowAi
      });
      const savedResult = await setWorkflowResult(message.jobLead.id, "sponsorship", result);
      return { ok: true, workflow: "sponsorship", result: savedResult };
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
    const savedResult = await setWorkflowResult(message.jobLead.id, "resume", result);
    return { ok: true, workflow: "resume", result: savedResult };
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
): Promise<Awaited<ReturnType<typeof analyzeSponsorship>>>;
async function setWorkflowResult(
  jobId: string,
  workflow: "resume",
  result: Awaited<ReturnType<typeof tailorResume>>
): Promise<Awaited<ReturnType<typeof tailorResume>>>;
async function setWorkflowResult(
  jobId: string,
  workflow: "sponsorship" | "resume",
  result: Awaited<ReturnType<typeof analyzeSponsorship>> | Awaited<ReturnType<typeof tailorResume>>
): Promise<Awaited<ReturnType<typeof analyzeSponsorship>> | Awaited<ReturnType<typeof tailorResume>>> {
  const state = await loadWorkspaceState();
  let savedResult = result;
  await saveWorkspaceState(
    updateWorkspaceJob(state, jobId, (job) => {
      if (workflow === "sponsorship") {
        const nextResult = result as Awaited<ReturnType<typeof analyzeSponsorship>>;
        const existingResult = job.workflows.sponsorship.result;
        if (!nextResult.ai_used && existingResult?.ai_used) {
          savedResult = existingResult;
          return {
            ...job,
            updatedAt: new Date().toISOString(),
            workflows: {
              ...job.workflows,
              sponsorship: {
                status: "completed",
                updatedAt: new Date().toISOString(),
                traceId: existingResult.trace_id,
                result: existingResult,
                error: ""
              }
            }
          };
        }
      }

      return {
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
      };
    })
  );
  return savedResult;
}
