import assert from "node:assert/strict";

import {
  canonicalizeLinkedInJobUrl,
  captureFormFieldAnswer,
  cleanLinkedInJobDescriptionText,
  extractLinkedInJobDescriptionFromRoot,
  extractLinkedInJobId,
  resetFormFieldRegistryForTest,
  resolveCaptureText,
  resolveSelectedText,
  scanFormFields
} from "../src/lib/form-context.ts";
import { assertFormCaptureBinding } from "../src/lib/page-capture.ts";
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
            ... more
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
  assert.doesNotMatch(text, /\.\.\. more/);
});

test("cleanLinkedInJobDescriptionText removes LinkedIn visual expand label but keeps JD sections", () => {
  const text = cleanLinkedInJobDescriptionText(`
    About the job
    First paragraph.
    ... more
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

test("scanFormFields skips value option and text reads until explicit capture", () => {
  resetFormFieldRegistryForTest();
  const readCounts = { value: 0, options: 0, selectedOptions: 0, textContent: 0, buttonText: 0 };
  installScanDocument({
    locationHref: "https://example.com/apply",
    title: "Apply",
    controls: [
      createLabeledTextInput({
        id: "full-name",
        label: "Full name",
        value: "Alice",
        readCounts
      }),
      createSelectField({
        id: "country",
        label: "Country of residence",
        value: "US",
        options: ["United States", "Canada"],
        readCounts
      })
    ]
  });

  const fields = scanFormFields();
  assert.ok(Array.isArray(fields));
  assert.equal(fields.length, 2);
  assert.equal(fields[0].questionText, "Full name");
  assert.equal(fields[1].inputType, "select");
  assert.equal(readCounts.value, 0);
  assert.equal(readCounts.options, 0);
  assert.equal(readCounts.selectedOptions, 0);
  assert.equal(readCounts.textContent, 0);

  const captured = captureFormFieldAnswer(fields[0].fieldId);
  assert.deepEqual(captured.answers, ["Alice"]);
  assert.equal(readCounts.value, 1);
});

test("scanFormFields merges same-name radios and checkboxes under fieldset legend", () => {
  resetFormFieldRegistryForTest();
  installScanDocument({
    locationHref: "https://example.com/apply",
    title: "Apply",
    controls: [
      createChoiceGroup({
        name: "workAuth",
        type: "radio",
        legend: "Are you legally authorized to work in the United States?",
        options: [
          { value: "Yes", checked: true },
          { value: "No", checked: false }
        ]
      }),
      createChoiceGroup({
        name: "benefits",
        type: "checkbox",
        legend: "Benefits",
        options: [
          { value: "Health", checked: true },
          { value: "Dental", checked: false }
        ]
      })
    ]
  });

  const fields = scanFormFields();
  assert.equal(fields.length, 2);
  assert.equal(fields[0].inputType, "radio");
  assert.equal(fields[1].inputType, "checkbox");

  const radioAnswers = captureFormFieldAnswer(fields[0].fieldId);
  const checkboxAnswers = captureFormFieldAnswer(fields[1].fieldId);
  assert.deepEqual(radioAnswers.answers, ["Yes"]);
  assert.deepEqual(checkboxAnswers.answers, ["Health"]);
});

test("custom select without reliable label is manual only while labeled custom select can capture on demand", () => {
  resetFormFieldRegistryForTest();
  const readCounts = { value: 0, options: 0, selectedOptions: 0, textContent: 0, buttonText: 0 };
  installScanDocument({
    locationHref: "https://example.com/apply",
    title: "Apply",
    controls: [
      createCustomSelect({
        id: "custom-1",
        label: "",
        valueText: "Choose one",
        readCounts
      }),
      createCustomSelect({
        id: "custom-2",
        label: "Country",
        valueText: "United States",
        readCounts
      })
    ]
  });

  const fields = scanFormFields();
  assert.equal(fields.length, 2);
  assert.equal(fields[0].inputType, "custom_select");
  assert.equal(fields[0].questionText, "");
  assert.equal(fields[0].recognitionConfidence, 0);
  assert.equal(fields[1].questionText, "Country");
  assert.equal(readCounts.buttonText, 0);

  assert.throws(() => captureFormFieldAnswer(fields[0].fieldId), /manually select/i);
  const captured = captureFormFieldAnswer(fields[1].fieldId);
  assert.deepEqual(captured.answers, ["United States"]);
  assert.equal(readCounts.buttonText, 1);
});

test("captureFormFieldAnswer throws when registry entry is stale", () => {
  resetFormFieldRegistryForTest();
  installScanDocument({
    locationHref: "https://example.com/apply",
    title: "Apply",
    controls: [createLabeledTextInput({ id: "email", label: "Email", value: "a@example.com", readCounts: freshReadCounts() })]
  });

  const fields = scanFormFields();
  fields[0].fieldId = "missing";
  assert.throws(() => captureFormFieldAnswer(fields[0].fieldId), /rescan/i);
});

test("same-name choices stay separate by fieldset and use the legend instead of option labels", () => {
  resetFormFieldRegistryForTest();
  installScanDocument({
    locationHref: "https://example.com/apply",
    title: "Apply",
    controls: [
      createChoiceGroup({
        name: "eligibility",
        type: "radio",
        legend: "Are you legally authorized to work?",
        options: [{ value: "Yes", checked: true }]
      }),
      createChoiceGroup({
        name: "eligibility",
        type: "radio",
        legend: "Will you require visa sponsorship?",
        options: [{ value: "Yes", checked: false }]
      })
    ]
  });

  const fields = scanFormFields();
  assert.equal(fields.length, 2);
  assert.deepEqual(fields.map((field) => field.questionText), [
    "Are you legally authorized to work?",
    "Will you require visa sponsorship?"
  ]);
});

test("choice groups without a legend do not use an individual option label as the question", () => {
  resetFormFieldRegistryForTest();
  const choice = createChoiceGroup({
    name: "eligibility",
    type: "radio",
    legend: "",
    options: [{ value: "Yes", checked: true }]
  });
  choice.elements[0].closest = (selector) => (selector === "label" ? makeLabel("Yes") : choice.elements[0].parentElement);
  installScanDocument({
    locationHref: "https://example.com/apply",
    title: "Apply",
    controls: [choice]
  });

  assert.deepEqual(scanFormFields(), []);
});

test("wrapping label removes nested controls from a clone without reading the live control text", () => {
  resetFormFieldRegistryForTest();
  const control = createNestedWrappingLabelInput();
  installScanDocument({
    locationHref: "https://example.com/apply",
    title: "Apply",
    controls: [control]
  });

  const fields = scanFormFields();
  assert.equal(fields[0].questionText, "Preferred name");
});

test("capture rejects a page navigation or disconnected scanned field", () => {
  resetFormFieldRegistryForTest();
  const readCounts = freshReadCounts();
  const control = createLabeledTextInput({ id: "email", label: "Email", value: "a@example.com", readCounts });
  installScanDocument({ locationHref: "https://example.com/apply", title: "Apply", controls: [control] });
  const [field] = scanFormFields();

  globalThis.window.location.href = "https://example.com/other";
  assert.throws(() => captureFormFieldAnswer(field.fieldId), /rescan/i);

  globalThis.window.location.href = "https://example.com/apply";
  const [rescanned] = scanFormFields();
  control.elements[0].isConnected = false;
  assert.throws(() => captureFormFieldAnswer(rescanned.fieldId), /rescan/i);
  assert.equal(readCounts.value, 0);
});

test("a later scan batch invalidates an earlier field ID on the same page", () => {
  resetFormFieldRegistryForTest();
  const control = createLabeledTextInput({
    id: "phone",
    label: "Phone",
    value: "555-0100",
    readCounts: freshReadCounts()
  });
  installScanDocument({ locationHref: "https://example.com/apply", title: "Apply", controls: [control] });
  const [first] = scanFormFields();
  const [second] = scanFormFields();

  assert.notEqual(first.fieldId, second.fieldId);
  assert.throws(() => captureFormFieldAnswer(first.fieldId), /rescan/i);
});

test("capture binding rejects another active tab or a navigated tab", () => {
  assert.throws(
    () => assertFormCaptureBinding({ tabId: 7, url: "https://example.com/apply" }, { id: 8, url: "https://example.com/apply" }),
    /rescan/i
  );
  assert.throws(
    () => assertFormCaptureBinding({ tabId: 7, url: "https://example.com/apply" }, { id: 7, url: "https://example.com/other" }),
    /rescan/i
  );
  assert.doesNotThrow(() =>
    assertFormCaptureBinding({ tabId: 7, url: "https://example.com/apply" }, { id: 7, url: "https://example.com/apply" })
  );
});

for (const { name, fn } of tests) {
  fn();
  console.log(`ok - ${name}`);
}

function freshReadCounts() {
  return { value: 0, options: 0, selectedOptions: 0, textContent: 0, buttonText: 0 };
}

function installScanDocument({ locationHref, title, controls }) {
  const body = { innerText: "Body text" };
  const form = makeElement("form", { textContent: "" });
  const labelsByFor = new Map();
  const ids = new Map();
  const allControls = [];

  for (const control of controls) {
    allControls.push(...control.elements);
    for (const [id, label] of control.labelsByFor.entries()) labelsByFor.set(id, label);
    for (const [id, node] of control.ids.entries()) ids.set(id, node);
  }

  globalThis.window = {
    location: { href: locationHref, hostname: "example.com" },
    getSelection: () => ({ toString: () => "" }),
    addEventListener() {},
    getComputedStyle: () => ({ visibility: "visible", display: "block" })
  };
  globalThis.document = {
    body,
    title,
    activeElement: null,
    addEventListener() {},
    querySelectorAll(selector) {
      if (selector === "input, textarea, select, button[aria-haspopup=\"listbox\"]") return allControls;
      const match = selector.match(/^label\[for="(.+)"\]$/);
      if (match) return labelsByFor.get(match[1]) ? [labelsByFor.get(match[1])] : [];
      return [];
    },
    querySelector(selector) {
      const match = selector.match(/^label\[for="(.+)"\]$/);
      if (match) return labelsByFor.get(match[1]) ?? null;
      return null;
    },
    getElementById(id) {
      return ids.get(id) ?? null;
    }
  };
  globalThis.CSS = { escape: (value) => value };
  form.ownerDocument = globalThis.document;
}

function createLabeledTextInput({ id, label, value, readCounts }) {
  const labelNode = makeLabel(label);
  const input = makeInput({
    id,
    type: "text",
    name: id,
    value,
    readCounts,
    required: true
  });
  return {
    elements: [input],
    labelsByFor: new Map([[id, labelNode]]),
    ids: new Map([[id, input]])
  };
}

function createSelectField({ id, label, value, options, readCounts }) {
  const labelNode = makeLabel(label);
  const select = makeSelect({ id, name: id, value, options, readCounts });
  return {
    elements: [select],
    labelsByFor: new Map([[id, labelNode]]),
    ids: new Map([[id, select]])
  };
}

function createChoiceGroup({ name, type, legend, options }) {
  const fieldset = makeElement("fieldset", {});
  const legendNode = makeElement("legend", { textContent: legend, parentElement: fieldset });
  fieldset.querySelector = (selector) => (selector === "legend" ? legendNode : null);
  const elements = options.map((option, index) =>
    makeInput({
      id: `${name}-${index}`,
      type,
      name,
      value: option.value,
      checked: option.checked,
      readCounts: freshReadCounts(),
      fieldset
    })
  );
  return {
    elements,
    labelsByFor: new Map(),
    ids: new Map(elements.map((element) => [element.id, element]))
  };
}

function createCustomSelect({ id, label, valueText, readCounts }) {
  const labelNode = label ? makeLabel(label) : null;
  const button = makeButton({ id, valueText, readCounts });
  return {
    elements: [button],
    labelsByFor: label ? new Map([[id, labelNode]]) : new Map(),
    ids: new Map([[id, button]])
  };
}

function createNestedWrappingLabelInput() {
  let removed = false;
  const label = {
    cloneNode() {
      return {
        querySelectorAll() {
          return [
            {
              remove() {
                removed = true;
              }
            }
          ];
        },
        get textContent() {
          return removed ? "Preferred name" : "Preferred name hidden control";
        }
      };
    }
  };
  Object.defineProperty(label, "textContent", {
    get() {
      throw new Error("scan must not read live wrapping label text");
    }
  });
  const input = makeInput({
    id: "preferred-name",
    type: "text",
    name: "preferred-name",
    value: "Ada",
    readCounts: freshReadCounts()
  });
  input.closest = (selector) => (selector === "label" ? label : null);
  return {
    elements: [input],
    labelsByFor: new Map(),
    ids: new Map([[input.id, input]])
  };
}

function makeLabel(text) {
  return {
    textContent: text,
    cloneNode() {
      return { textContent: text, querySelectorAll: () => [] };
    }
  };
}

function makeInput({ id, type, name, value, checked = false, readCounts, required = false, fieldset = null }) {
  const element = makeElement("input", {
    id,
    parentElement: fieldset,
    required,
    getAttribute(nameAttr) {
      if (nameAttr === "type") return type;
      if (nameAttr === "name") return name;
      if (nameAttr === "aria-labelledby") return "";
      if (nameAttr === "autocomplete") return "";
      return "";
    }
  });
  Object.defineProperty(element, "value", {
    get() {
      readCounts.value += 1;
      return value;
    }
  });
  element.checked = checked;
  return element;
}

function makeSelect({ id, name, value, options, readCounts }) {
  const element = makeElement("select", {
    id,
    required: false,
    getAttribute(nameAttr) {
      if (nameAttr === "name") return name;
      if (nameAttr === "aria-labelledby") return "";
      return "";
    }
  });
  Object.defineProperty(element, "value", {
    get() {
      readCounts.value += 1;
      return value;
    }
  });
  Object.defineProperty(element, "options", {
    get() {
      readCounts.options += 1;
      return options.map((option) => ({ text: option, value: option }));
    }
  });
  Object.defineProperty(element, "selectedOptions", {
    get() {
      readCounts.selectedOptions += 1;
      return [{ text: value }];
    }
  });
  return element;
}

function makeButton({ id, valueText, readCounts }) {
  const element = makeElement("button", {
    id,
    getAttribute(nameAttr) {
      if (nameAttr === "aria-haspopup") return "listbox";
      if (nameAttr === "aria-labelledby") return "";
      return "";
    }
  });
  Object.defineProperty(element, "textContent", {
    get() {
      readCounts.buttonText += 1;
      return valueText;
    }
  });
  return element;
}

function makeElement(tagName, overrides) {
  return {
    tagName: tagName.toUpperCase(),
    parentElement: null,
    children: [],
    required: false,
    matches(selector) {
      return selector === tagName || selector === tagName.toLowerCase();
    },
    closest(selector) {
      if (selector === "label") return null;
      if (selector === "fieldset") return this.parentElement?.tagName === "FIELDSET" ? this.parentElement : null;
      return null;
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    cloneNode() {
      return {
        querySelectorAll: () => [],
        removeChild() {},
        textContent: ""
      };
    },
    getBoundingClientRect() {
      return { width: 120, height: 32 };
    },
    dispatchEvent() {},
    ...overrides
  };
}
