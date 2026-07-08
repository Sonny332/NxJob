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
    action: "" | "update_existing" | "create_new";
    requires_user_choice: boolean;
    warnings: string[];
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
  ai_reasoning_effort: string;
  ai_profile_id: string;
  ai_profile_display_name: string;
  ai_provider_source: string;
  resume_output_dir_configured: boolean;
  resume_output_dir: string;
  dol_cache_dir_configured: boolean;
  dol_cache_dir_source: string;
  dol_cache_dir: string;
  public_lookup_available: boolean;
  dol_index_status: DolIndexStatus;
  warnings: string[];
};

export type DolIndexSelectedFile = {
  fy: number;
  quarter: number | null;
  url: string;
  path: string;
  size_bytes: number;
};

export type DolIndexJob = {
  job_id: string;
  status: string;
  phase: string;
  message: string;
  error: string;
  started_at: string;
  completed_at: string;
  progress_current: number;
  progress_total: number;
};

export type DolIndexStatus = {
  status: string;
  cache_dir: string;
  active_index_ready: boolean;
  fingerprint: string;
  index_schema_version: number;
  last_built_at: string;
  last_checked_at: string;
  expires_at: string;
  row_count: number;
  cache_size_bytes: number;
  max_cache_bytes: number;
  selected_files: DolIndexSelectedFile[];
  warnings: string[];
  current_job: DolIndexJob | null;
};

export type DolIndexStatusResponse = DolIndexStatus & {
  trace_id: string;
};

export type DolIndexBuildResponse = DolIndexJob & {
  trace_id: string;
};

export type DolIndexJobResponse = DolIndexJob & {
  trace_id: string;
};

export type DolIndexCleanupResponse = {
  trace_id: string;
  deleted_files: string[];
  freed_bytes: number;
  warnings: string[];
};

export type AiProviderProfileRecord = {
  id: string;
  display_name: string;
  provider: string;
  base_url: string;
  model: string;
  reasoning_effort: string;
  source: string;
  is_active: boolean;
};

export type AiProviderProfilesResponse = {
  trace_id: string;
  profiles: AiProviderProfileRecord[];
  active_profile_id: string;
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

export type ApplicationListResponse = {
  trace_id: string;
  applications: ApplicationRecord[];
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

export type OutcomeSignalListResponse = {
  trace_id: string;
  outcomes: OutcomeSignalRecord[];
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
    field_id: string;
    field_label: string;
    question_text: string;
    intent: string;
    answer_type: string;
    confidence: number;
    selected_option: string;
    evidence_summary: string[];
    answer: string;
    referenced_bullets: string[];
    risk_flags: string[];
    requires_user_review: boolean;
  };
  ai_used: boolean;
};

export type FormAnswerDraftsResponse = {
  trace_id: string;
  drafts: FormAnswerDraftResponse["draft"][];
  ai_used: boolean;
  warnings: string[];
};

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`NxJob local service returned ${response.status}.`);
  }

  return response.json() as Promise<HealthResponse>;
}

export async function captureJobLead(
  context: PageContext,
  options: { duplicateAction?: "" | "update_existing" | "create_new" } = {}
): Promise<CaptureJobLeadResponse> {
  if (context.selectedText.length > 0 && context.selectedText.length < 400) {
    throw new Error("Selected JD text is shorter than 400 characters. Expand the selection, then retry capture.");
  }
  if (!context.captureText.trim()) {
    throw new Error(context.captureWarnings[0] || "Captured JD text is too short. Open the full job description, then retry capture.");
  }

  const useSelectedText = context.captureSource === "selected_text";
  const response = await fetch(`${API_BASE_URL}/api/v1/job-leads/capture`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      source_url: context.canonicalUrl || context.url,
      source_site: inferSourceSite(context.url),
      page_title: context.title,
      job_title: context.jobTitle ?? "",
      company_name: context.companyName ?? "",
      location: context.location ?? "",
      selected_text: useSelectedText ? context.captureText : "",
      page_text_excerpt: useSelectedText ? "" : context.captureText,
      platform_insights: {},
      capture_metadata: {
        source: context.captureSource,
        extractor: context.captureExtractor,
        text_length: context.captureText.length,
        raw_url: context.rawUrl || context.url,
        canonical_url: context.canonicalUrl || context.url,
        linkedin_job_id: context.linkedinJobId || "",
        warnings: context.captureWarnings,
        confidence: context.metadataConfidence ?? 0,
        metadata_source: context.metadataSource ?? ""
      },
      duplicate_action: options.duplicateAction ?? "",
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

export async function listApplications(options: { jobLeadId: string; limit?: number }): Promise<ApplicationListResponse> {
  const params = new URLSearchParams();
  params.set("job_lead_id", options.jobLeadId);
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/applications?${params.toString()}`);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ApplicationListResponse>;
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

export async function listOutcomes(options: { jobLeadId: string; limit?: number }): Promise<OutcomeSignalListResponse> {
  const params = new URLSearchParams();
  params.set("job_lead_id", options.jobLeadId);
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/outcomes?${params.toString()}`);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<OutcomeSignalListResponse>;
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
  options: { forceRefresh?: boolean; allowAi?: boolean } = {}
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
      allow_public_lookup: true,
      allow_ai: options.allowAi ?? true,
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
  displayName?: string;
  reasoningEffort?: string;
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
      api_key: payload.apiKey,
      display_name: payload.displayName ?? "",
      reasoning_effort: payload.reasoningEffort ?? "medium"
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<ConfigStatusResponse>;
}

export async function getDolIndexStatus(): Promise<DolIndexStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/dol/index/status`);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<DolIndexStatusResponse>;
}

export async function buildDolIndex(): Promise<DolIndexBuildResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/dol/index/build`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ force: true })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<DolIndexBuildResponse>;
}

export async function getDolIndexJob(jobId: string): Promise<DolIndexJobResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/dol/index/jobs/${encodeURIComponent(jobId)}`);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<DolIndexJobResponse>;
}

export async function cleanupDolIndex(): Promise<DolIndexCleanupResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/dol/index/cleanup`, {
    method: "POST"
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<DolIndexCleanupResponse>;
}

export async function listAiProviderProfiles(): Promise<AiProviderProfilesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/ai-profiles`);

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<AiProviderProfilesResponse>;
}

export async function activateAiProviderProfile(profileId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/ai-profiles/${encodeURIComponent(profileId)}/activate`, {
    method: "POST"
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }
}

export async function deleteAiProviderProfile(profileId: string): Promise<ConfigStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/ai-profiles/${encodeURIComponent(profileId)}`, {
    method: "DELETE"
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

export async function saveDolCacheDirectory(path: string): Promise<ConfigStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/dol-cache-directory`, {
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
        field_id: fieldContext.fieldId,
        label: fieldContext.label,
        question_text: fieldContext.questionText ?? "",
        placeholder: fieldContext.placeholder,
        surrounding_text: fieldContext.surroundingText,
        current_value: fieldContext.currentValue,
        input_type: fieldContext.inputType,
        required: fieldContext.required ?? false,
        options: fieldContext.options ?? [],
        sensitive_kind: fieldContext.sensitiveKind ?? ""
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

export async function draftFormAnswers(
  jobLead: JobLeadRecord,
  fields: FieldContext[]
): Promise<FormAnswerDraftsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/forms/draft-answers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      job_lead_id: jobLead.id,
      fields: fields.map((field) => ({
        field_id: field.fieldId,
        label: field.label,
        question_text: field.questionText ?? "",
        placeholder: field.placeholder,
        surrounding_text: field.surroundingText,
        current_value: field.currentValue,
        input_type: field.inputType,
        required: field.required ?? false,
        options: field.options ?? [],
        sensitive_kind: field.sensitiveKind ?? ""
      })),
      jd_text: jobLead.jd_text,
      profile_vault_id: "master_default"
    })
  });

  if (!response.ok) {
    const message = await readErrorMessage(response);
    throw new Error(message);
  }

  return response.json() as Promise<FormAnswerDraftsResponse>;
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
    const body = (await response.json()) as {
      detail?: string | { message?: string; error?: { message?: string } };
      error?: { message?: string };
    };
    if (typeof body.detail === "object" && body.detail !== null) {
      return body.detail.error?.message ?? body.detail.message ?? `NxJob local service returned ${response.status}.`;
    }
    return body.error?.message ?? body.detail ?? `NxJob local service returned ${response.status}.`;
  } catch {
    return `NxJob local service returned ${response.status}.`;
  }
}

