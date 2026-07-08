import assert from "node:assert/strict";

import {
  canonicalizeLinkedInJobUrl,
  cleanLinkedInJobDescriptionText,
  extractLinkedInJobDescriptionFromRoot,
  extractLinkedInJobId,
  resolveCaptureText,
  resolveSelectedText
} from "../src/lib/form-context.ts";
import { createWorkspaceRecord, emptyWorkflow, upsertWorkspaceJob } from "../src/lib/workspace-state.ts";

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

test("extractLinkedInJobId parses LinkedIn jobs search-results currentJobId", () => {
  const url = "https://www.linkedin.com/jobs/search-results/?keywords=engineer&currentJobId=103644278";
  assert.equal(extractLinkedInJobId(url), "103644278");
  assert.equal(canonicalizeLinkedInJobUrl(url), "https://www.linkedin.com/jobs/view/103644278/");
});

test("extractLinkedInJobDescriptionFromRoot reads search-results side panel description", () => {
  const root = {
    querySelector(selector) {
      if (selector === ".jobs-search__job-details--container .jobs-box__html-content") {
        return { textContent: "Senior Engineer Full job description goes here." };
      }
      return null;
    }
  };

  assert.equal(
    extractLinkedInJobDescriptionFromRoot(root),
    "Senior Engineer Full job description goes here."
  );
});

test("extractLinkedInJobDescriptionFromRoot reads single-job About the job section without clicking expand", () => {
  const root = {
    querySelector(selector) {
      if (selector === '[componentkey^="JobDetails_AboutTheJob_"]') {
        return {
          textContent: `
            About the job
            Gencor is seeking an experienced Thermal Engineer.
            Key Responsibilities:
            Design and optimize thermal systems.
            … more
            Benefits found in job post
            Vision insurance, 401(k)
            Requirements added by the job poster
            Bachelor's Degree
          `
        };
      }
      return null;
    }
  };

  const text = extractLinkedInJobDescriptionFromRoot(root);

  assert.match(text, /Gencor is seeking an experienced Thermal Engineer/);
  assert.match(text, /Benefits found in job post Vision insurance, 401\(k\)/);
  assert.match(text, /Requirements added by the job poster Bachelor's Degree/);
  assert.doesNotMatch(text, /\.\.\. more|… more/);
});

test("cleanLinkedInJobDescriptionText removes LinkedIn visual expand label but keeps JD sections", () => {
  const text = cleanLinkedInJobDescriptionText(`
    About the job
    First paragraph.
    … more
    Benefits found in job post
    Medical insurance
    Requirements added by the job poster
    Work authorization required
  `);

  assert.equal(
    text,
    "First paragraph. Benefits found in job post Medical insurance Requirements added by the job poster Work authorization required"
  );
});

test("resolveSelectedText falls back to recent cached selection only when live selection is lost", () => {
  assert.equal(resolveSelectedText("live selection", "cached selection"), "live selection");
  assert.equal(resolveSelectedText("", "cached selection"), "cached selection");
});

test("extractLinkedInJobDescriptionFromRoot does not need LinkedIn expand control text", () => {
  const root = {
    querySelector(selector) {
      if (selector === '[componentkey^="JobDetails_AboutTheJob_"]') {
        return {
          textContent: "About the job Full JD text is already present in DOM. Benefits found in job post Medical insurance"
        };
      }
      return null;
    }
  };

  assert.equal(
    extractLinkedInJobDescriptionFromRoot(root),
    "Full JD text is already present in DOM. Benefits found in job post Medical insurance"
  );
});

test("resolveCaptureText keeps selected text priority when cached selection is long enough", () => {
  const capture = resolveCaptureText({
    selectedText: resolveSelectedText("", "A".repeat(450)),
    linkedInDescription: "B".repeat(900),
    pageText: "C".repeat(1200),
    linkedInJobId: "103644278"
  });

  assert.equal(capture.source, "selected_text");
  assert.equal(capture.extractor, "user_selection");
  assert.equal(capture.text.length, 450);
});

test("resolveCaptureText rejects short LinkedIn auto capture text", () => {
  const capture = resolveCaptureText({
    selectedText: "",
    linkedInDescription: "Short LinkedIn excerpt",
    pageText: "C".repeat(1200),
    linkedInJobId: "103644278"
  });

  assert.equal(capture.text, "");
  assert.equal(capture.source, "linkedin_job_detail");
  assert.equal(capture.extractor, "linkedin_auto");
  assert.match(capture.warnings[0], /shorter than 800/);
});

test("resolveCaptureText rejects short generic page excerpt", () => {
  const capture = resolveCaptureText({
    selectedText: "",
    linkedInDescription: "",
    pageText: "Short generic page",
    linkedInJobId: ""
  });

  assert.equal(capture.text, "");
  assert.equal(capture.source, "page_text_excerpt");
  assert.equal(capture.extractor, "generic_page_excerpt");
  assert.match(capture.warnings[0], /shorter than 800/);
});

function captureSummary(overrides = {}) {
  return {
    isDuplicate: false,
    existingJobLeadId: "",
    dedupeAction: "",
    requiresUserChoice: false,
    warnings: [],
    jdSource: "selected_text",
    jdLength: 800,
    ...overrides
  };
}

function aiSponsorshipRun() {
  return {
    status: "completed",
    updatedAt: "2026-07-07T10:00:00.000Z",
    traceId: "trc-ai",
    result: {
      trace_id: "trc-ai",
      sponsorship: {
        status: "needs_confirmation",
        confidence: 0.78,
        summary: "AI review found mixed evidence.",
        risk_flags: [],
        questions_to_confirm: ["Confirm sponsorship support."],
        is_legal_conclusion: false
      },
      evidence: [
        {
          source: "ai_inference",
          evidence_text: "AI review result",
          evidence_url: "",
          confidence: 0.78
        }
      ],
      ai_used: true,
      cache: { hit: false, cache_key: "ai-cache" }
    },
    error: ""
  };
}

function localSponsorshipRun() {
  return {
    ...emptyWorkflow(),
    status: "completed",
    updatedAt: "2026-07-07T10:05:00.000Z",
    traceId: "trc-local",
    result: {
      trace_id: "trc-local",
      sponsorship: {
        status: "needs_confirmation",
        confidence: 0.52,
        summary: "Local precheck found generic work authorization wording.",
        risk_flags: [],
        questions_to_confirm: ["Confirm sponsorship support."],
        is_legal_conclusion: false
      },
      evidence: [
        {
          source: "jd_text",
          evidence_text: "authorized to work in the United States",
          evidence_url: "",
          confidence: 0.52
        }
      ],
      ai_used: false,
      cache: { hit: false, cache_key: "local-cache" }
    },
    error: ""
  };
}

test("upsertWorkspaceJob keeps existing AI sponsorship result during duplicate same-JD update_existing merge", () => {
  const baseJobLead = {
    id: "job-1",
    source_url: "https://www.linkedin.com/jobs/view/103644278/",
    source_site: "linkedin",
    page_title: "Software Engineer",
    company_name: "Acme Data Inc",
    job_title: "Software Engineer",
    location: "Seattle, WA",
    captured_at: "2026-07-07T00:00:00.000Z",
    jd_text: "Original JD text",
    jd_hash: "jd-hash-1",
    platform_insights: {},
    search_query: "",
    status: "captured",
    user_notes: ""
  };
  const existingRecord = createWorkspaceRecord({
    jobLead: baseJobLead,
    pageTitle: "Original title",
    pageUrl: baseJobLead.source_url,
    selectedTextLength: 800,
    pageTextLength: 1000,
    capture: captureSummary()
  });
  existingRecord.workflows.sponsorship = aiSponsorshipRun();

  const incomingRecord = createWorkspaceRecord({
    jobLead: { ...baseJobLead, page_title: "Updated title" },
    pageTitle: "Updated title",
    pageUrl: baseJobLead.source_url,
    selectedTextLength: 900,
    pageTextLength: 1200,
    capture: captureSummary({
      isDuplicate: true,
      existingJobLeadId: "job-1",
      dedupeAction: "update_existing",
      jdSource: "page_text_excerpt",
      jdLength: 900
    })
  });
  incomingRecord.workflows.sponsorship = localSponsorshipRun();

  const nextState = upsertWorkspaceJob(
    { focusedJobId: existingRecord.id, showHidden: false, jobs: [existingRecord] },
    incomingRecord
  );

  assert.equal(nextState.jobs.length, 1);
  assert.equal(nextState.jobs[0].workflows.sponsorship.traceId, "trc-ai");
  assert.equal(nextState.jobs[0].workflows.sponsorship.result?.ai_used, true);
  assert.equal(nextState.jobs[0].capture.dedupeAction, "update_existing");
});

test("upsertWorkspaceJob clears workflow results when update_existing changes JD hash", () => {
  const baseJobLead = {
    id: "job-1",
    source_url: "https://www.linkedin.com/jobs/view/103644278/",
    source_site: "linkedin",
    page_title: "Software Engineer",
    company_name: "Acme Data Inc",
    job_title: "Software Engineer",
    location: "Seattle, WA",
    captured_at: "2026-07-07T00:00:00.000Z",
    jd_text: "Original JD text",
    jd_hash: "jd-hash-1",
    platform_insights: {},
    search_query: "",
    status: "captured",
    user_notes: ""
  };
  const existingRecord = createWorkspaceRecord({
    jobLead: baseJobLead,
    pageTitle: "Original title",
    pageUrl: baseJobLead.source_url,
    selectedTextLength: 800,
    pageTextLength: 1000,
    capture: captureSummary()
  });
  existingRecord.workflows.sponsorship = aiSponsorshipRun();

  const incomingRecord = createWorkspaceRecord({
    jobLead: { ...baseJobLead, jd_text: "New JD text", jd_hash: "jd-hash-2" },
    pageTitle: "Original title",
    pageUrl: baseJobLead.source_url,
    selectedTextLength: 900,
    pageTextLength: 1200,
    capture: captureSummary({
      isDuplicate: true,
      existingJobLeadId: "job-1",
      dedupeAction: "update_existing",
      jdSource: "page_text_excerpt",
      jdLength: 900
    })
  });
  incomingRecord.workflows.sponsorship = localSponsorshipRun();

  const nextState = upsertWorkspaceJob(
    { focusedJobId: existingRecord.id, showHidden: false, jobs: [existingRecord] },
    incomingRecord
  );

  assert.equal(nextState.jobs[0].workflows.sponsorship.status, "idle");
  assert.equal(nextState.jobs[0].workflows.sponsorship.result, null);
  assert.equal(nextState.jobs[0].workflows.resume.result, null);
  assert.equal(nextState.jobs[0].workflows.formAnswer.result, null);
});

for (const { name, fn } of tests) {
  fn();
  console.log(`ok - ${name}`);
}
