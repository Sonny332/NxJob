import type { FieldContext } from "./form-context";
import type { PageContext } from "./page-capture";

const API_BASE_URL = "http://127.0.0.1:8765";

export type HealthResponse = {
  status: "ok";
  service: "nxjob-local-service";
  version: string;
};

export type SourceSite = "linkedin" | "indeed" | "company_ats" | "other";
export type ApplicationMethod =
  | "easy_apply"
  | "external_ats"
  | "email"
  | "other"
  | "linkedin_easy_apply"
  | "company_ats"
  | "manual";
export type ApplicationStatus =
  | "captured"
  | "reviewing"
  | "skipped"
  | "tailored"
  | "ready_to_apply"
  | "applied"
  | "replied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "closed";
export type OutcomeType = "positive_reply" | "screen" | "interview" | "offer" | "rejection" | "no_response" | "closed";
export type OutcomeSource = "email" | "manual" | "recruiter_message" | "calendar" | "other";

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

export type SponsorshipStatus =
  | "supports"
  | "does_not_support"
  | "likely_supports"
  | "likely_not_supports"
  | "needs_confirmation"
  | "unknown";

export type SponsorshipEvidenceItem = {
  source: string;
  evidence_text: string;
  evidence_url: string;
  confidence: number;
};

export type SponsorshipAnalyzeResponse = {
  trace_id: string;
  sponsorship: {
    status: SponsorshipStatus;
    confidence: number;
    summary: string;
    risk_flags: string[];
    questions_to_confirm: string[];
    is_legal_conclusion: boolean;
  };
  evidence: SponsorshipEvidenceItem[];
  ai_used: boolean;
  cache: WorkflowCacheInfo;
};

export type WorkflowCacheInfo = {
  hit: boolean;
  cache_key: string;
};

export type ResumeTailorResponse = {
  trace_id: string;
  resume_version: {
    id: string;
    file_path: string;
    format: "docx";
    selected_bullets: string[];
    change_summary: string;
  };
  used_success_references: string[];
  warnings: string[];
  ai_used: boolean;
  ai_provider_name: string;
  docx_path: string;
  markdown_path: string;
  filename_base: string;
  layout_budget: Record<string, unknown>;
  quality_checks: Record<string, unknown>;
  cache: WorkflowCacheInfo;
};

export type ConfigStatusResponse = {
  trace_id: string;
  master_resume_configured: boolean;
  master_resume_source: string;
  ai_provider_configured: boolean;
  ai_provider_name: string;
  ai_model: string;
  resume_output_dir_configured: boolean;
  resume_output_dir: string;
  public_lookup_available: boolean;
  warnings: string[];
};

export type WorkflowResultRecord = {
  id: string;
  job_lead_id: string;
  workflow_name: string;
  cache_key: string;
  created_at: string;
  trace_id: string;
  status: string;
  result_summary: string;
  response: Record<string, unknown>;
};

export type WorkflowResultsResponse = {
  trace_id: string;
  results: WorkflowResultRecord[];
};

export type ResumeFeedbackRating =
  | "good_fit"
  | "needs_stronger_match"
  | "too_generic"
  | "save_success_candidate"
  | "success_reference_candidate";

export type ResumeTailorFeedbackResponse = {
  trace_id: string;
  feedback: {
    id: string;
    job_lead_id: string;
    resume_version_id: string;
    created_at: string;
    rating: ResumeFeedbackRating;
    user_notes: string;
    candidate_status: string;
  };
};

export type ApplicationRecord = {
  id: string;
  job_lead_id: string;
  resume_version_id: string | null;
  applied_at: string;
  application_url: string;
  application_method: ApplicationMethod;
  status: ApplicationStatus;
  submitted_by_user: boolean;
  follow_up_at: string;
  user_notes: string;
};

export type ApplicationResponse = {
  trace_id: string;
  application: ApplicationRecord;
};

export type OutcomeSignalRecord = {
  id: string;
  application_id: string;
  job_lead_id: string;
  outcome_type: OutcomeType;
  outcome_at: string;
  source: OutcomeSource;
  evidence_text: string;
  evidence_url: string;
  user_notes: string;
  created_at: string;
};

export type OutcomeSignalResponse = {
  trace_id: string;
  outcome: OutcomeSignalRecord;
  success_reference: {
    created: boolean;
    id: string;
  };
};

export type SuccessReferenceRecord = {
  id: string;
  application_id: string;
  job_lead_id: string;
  resume_version_id: string;
  outcome_type: string;
  outcome_at: string;
  source: string;
  search_query: string;
  effective_keywords: string[];
  effective_bullets: string[];
  user_notes: string;
};

export type SuccessReferenceListResponse = {
  trace_id: string;
  success_references: SuccessReferenceRecord[];
};

export type FormAnswerDraftResponse = {
  trace_id: string;
  draft: {
    id: string;
    answer: string;
    referenced_bullets: string[];
    risk_flags: string[];
    requires_user_review: boolean;
  };
  ai_used: boolean;
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

export async function getJobLead(jobLeadId: string): Promise<JobLeadRecord> {
  const response = await fetch(`${API_BASE_URL}/api/v1/job-leads/${encodeURIComponent(jobLeadId)}`);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<JobLeadRecord>;
}

export async function getWorkflowResults(jobLeadId: string): Promise<WorkflowResultsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/job-leads/${encodeURIComponent(jobLeadId)}/workflow-results`
  );

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<WorkflowResultsResponse>;
}

export async function createApplication(payload: {
  jobLeadId: string;
  resumeVersionId?: string | null;
  applicationUrl: string;
  applicationMethod: ApplicationMethod;
  submittedByUser?: boolean;
  userNotes?: string;
}): Promise<ApplicationResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/applications`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      job_lead_id: payload.jobLeadId,
      resume_version_id: payload.resumeVersionId ?? null,
      application_url: payload.applicationUrl,
      application_method: payload.applicationMethod,
      submitted_by_user: payload.submittedByUser ?? true,
      user_notes: payload.userNotes ?? ""
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ApplicationResponse>;
}

export async function createOutcome(payload: {
  applicationId?: string;
  jobLeadId: string;
  outcomeType: OutcomeType;
  source?: OutcomeSource;
  evidenceText?: string;
  evidenceUrl?: string;
  userNotes?: string;
}): Promise<OutcomeSignalResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/outcomes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      application_id: payload.applicationId ?? "",
      job_lead_id: payload.jobLeadId,
      outcome_type: payload.outcomeType,
      source: payload.source ?? "manual",
      evidence_text: payload.evidenceText ?? "",
      evidence_url: payload.evidenceUrl ?? "",
      user_notes: payload.userNotes ?? ""
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<OutcomeSignalResponse>;
}

export async function listSuccessReferences(options: { limit?: number } = {}): Promise<SuccessReferenceListResponse> {
  const params = new URLSearchParams();
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/v1/success-references${query ? `?${query}` : ""}`);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<SuccessReferenceListResponse>;
}

export async function analyzeSponsorship(
  jobLead: JobLeadRecord,
  context: PageContext | null,
  options: { forceRefresh?: boolean } = {}
): Promise<SponsorshipAnalyzeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/sponsorship/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      job_lead_id: jobLead.id,
      jd_text: jobLead.jd_text,
      company_name: jobLead.company_name,
      job_url: context?.url ?? jobLead.source_url,
      application_form_text: "",
      allow_public_lookup: false,
      allow_ai: true,
      force_refresh: options.forceRefresh ?? false
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<SponsorshipAnalyzeResponse>;
}

export async function tailorResume(
  jobLead: JobLeadRecord,
  options: { forceRefresh?: boolean } = {}
): Promise<ResumeTailorResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/resumes/tailor`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      job_lead_id: jobLead.id,
      force_refresh: options.forceRefresh ?? false
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ResumeTailorResponse>;
}

export function getResumeArtifactUrl(resumeVersionId: string, artifact: "docx" | "markdown"): string {
  return `${API_BASE_URL}/api/v1/resume-versions/${encodeURIComponent(resumeVersionId)}/artifacts/${artifact}`;
}

export async function checkConfigStatus(): Promise<ConfigStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/status`);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ConfigStatusResponse>;
}

export async function saveMasterResume(content: string, sourceFilename: string): Promise<ConfigStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/master-resume`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      content,
      source_filename: sourceFilename
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ConfigStatusResponse>;
}

export async function saveAiProvider(payload: {
  provider: string;
  baseUrl: string;
  model: string;
  apiKey: string;
}): Promise<ConfigStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/ai-provider`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      provider: payload.provider,
      base_url: payload.baseUrl,
      model: payload.model,
      api_key: payload.apiKey
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ConfigStatusResponse>;
}

export async function saveResumeOutputDirectory(path: string): Promise<ConfigStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/resume-output-directory`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ path })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ConfigStatusResponse>;
}

export async function clearAiProvider(): Promise<ConfigStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/ai-provider`, {
    method: "DELETE"
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ConfigStatusResponse>;
}

export async function submitResumeFeedback(payload: {
  jobLeadId: string;
  resumeVersionId: string;
  rating: ResumeFeedbackRating;
  userNotes?: string;
}): Promise<ResumeTailorFeedbackResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/resumes/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      job_lead_id: payload.jobLeadId,
      resume_version_id: payload.resumeVersionId,
      rating: payload.rating,
      user_notes: payload.userNotes ?? ""
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ResumeTailorFeedbackResponse>;
}

export async function draftFormAnswer(
  jobLead: JobLeadRecord,
  fieldContext: FieldContext
): Promise<FormAnswerDraftResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/forms/draft-answer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      job_lead_id: jobLead.id,
      field_context: {
        label: fieldContext.label,
        placeholder: fieldContext.placeholder,
        surrounding_text: fieldContext.surroundingText,
        current_value: fieldContext.currentValue,
        input_type: fieldContext.inputType
      },
      jd_text: jobLead.jd_text,
      profile_vault_id: "master_default"
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<FormAnswerDraftResponse>;
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

