const API_BASE_URL = "http://127.0.0.1:8765";

import type { PageContext } from "./page-capture";

export type HealthResponse = {
  status: "ok";
  service: "nxjob-local-service";
  version: string;
};

export type SourceSite = "linkedin" | "indeed" | "company_ats" | "other";

export type JobLeadRecord = {
  id: string;
  source_url: string;
  source_site: SourceSite;
  page_title: string;
  company_name: string;
  job_title: string;
  location: string;
  captured_at: string;
  jd_text: string;
  jd_hash: string;
  platform_insights: Record<string, unknown>;
  search_query: string;
  status: string;
  user_notes: string;
};

export type CaptureJobLeadResponse = {
  trace_id: string;
  job_lead: JobLeadRecord;
  dedupe: {
    is_duplicate: boolean;
    existing_job_lead_id: string | null;
  };
};

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`NxJob local service returned ${response.status}.`);
  }

  return response.json() as Promise<HealthResponse>;
}

export async function captureJobLead(context: PageContext): Promise<CaptureJobLeadResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/job-leads/capture`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      source_url: context.url,
      source_site: inferSourceSite(context.url),
      page_title: context.title,
      selected_text: context.selectedText,
      page_text_excerpt: context.pageTextExcerpt,
      platform_insights: {},
      search_query: "",
      user_notes: ""
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<CaptureJobLeadResponse>;
}

function inferSourceSite(url: string): SourceSite {
  try {
    const host = new URL(url).hostname.toLowerCase();
    if (host.includes("linkedin.")) return "linkedin";
    if (host.includes("indeed.")) return "indeed";
    if (host.includes("greenhouse.") || host.includes("lever.co") || host.includes("workdayjobs.")) {
      return "company_ats";
    }
  } catch {
    return "other";
  }

  return "other";
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string; error?: { message?: string } };
    return body.error?.message ?? body.detail ?? `NxJob local service returned ${response.status}.`;
  } catch {
    return `NxJob local service returned ${response.status}.`;
  }
}

