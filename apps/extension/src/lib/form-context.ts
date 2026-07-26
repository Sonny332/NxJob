export type PageContext = {
  url: string;
  title: string;
  jobTitle?: string;
  companyName?: string;
  location?: string;
  metadataSource?: string;
  metadataConfidence?: number;
  selectedText: string;
  captureText: string;
  captureSource: string;
  captureExtractor: string;
  captureWarnings: string[];
  rawUrl: string;
  canonicalUrl: string;
  linkedinJobId: string;
  pageTextExcerpt: string;
};

export type DetectedFormField = {
  fieldId: string;
  questionText: string;
  inputType: "text" | "textarea" | "radio" | "checkbox" | "select" | "custom_select";
  required: boolean;
  sensitiveKind: string;
  recognitionConfidence: number;
};

export type CapturedFormAnswer = {
  fieldId: string;
  answers: string[];
};

export type FieldContext = DetectedFormField & {
  label?: string;
  placeholder?: string;
  surroundingText?: string;
  currentValue?: string;
  options?: string[];
};

const MAX_TEXT_EXCERPT = 12000;
const MIN_SELECTED_TEXT_LENGTH = 400;
const MIN_AUTO_CAPTURE_TEXT_LENGTH = 800;
const MAX_FORM_FIELDS = 30;
const RECENT_SELECTION_MAX_AGE_MS = 30_000;

type RecentSelectionSnapshot = {
  text: string;
  href: string;
  capturedAt: number;
};

type QueryRoot = {
  querySelector(selector: string): ElementLike | null;
};

type ElementLike = {
  textContent?: string | null;
};

type ScanFieldElement = {
  tagName?: string;
  id?: string;
  required?: boolean;
  checked?: boolean;
  parentElement?: ScanFieldElement | null;
  children?: ScanFieldElement[];
  isConnected?: boolean;
  textContent?: string | null;
  value?: string;
  selectedOptions?: ArrayLike<{ text?: string | null; value?: string | null }>;
  options?: ArrayLike<{ text?: string | null; value?: string | null }>;
  getAttribute(name: string): string | null;
  closest(selector: string): ScanFieldElement | null;
  querySelector(selector: string): ScanFieldElement | null;
  querySelectorAll(selector: string): ArrayLike<ScanFieldElement>;
  cloneNode?(deep?: boolean): ScanFieldElement;
  removeChild?(child: ScanFieldElement): void;
  remove?(): void;
  getBoundingClientRect(): { width: number; height: number };
  dispatchEvent?(event: Event): void;
};

type FieldRegistryEntry = {
  field: DetectedFormField;
  questionText: string;
  reliableLabel: boolean;
  elements: ScanFieldElement[];
  pageUrl: string;
  batchId: number;
};

type JobMetadata = {
  jobTitle: string;
  companyName: string;
  location: string;
  source: string;
  confidence: number;
};

type CaptureTextResolution = {
  text: string;
  source: string;
  extractor: string;
  warnings: string[];
};

let recentSelectionSnapshot: RecentSelectionSnapshot = {
  text: "",
  href: "",
  capturedAt: 0
};

const fieldRegistry = new Map<string, FieldRegistryEntry>();
const fieldGroupScopes = new WeakMap<object, string>();
let fieldSequence = 0;
let scanBatchSequence = 0;
let fieldGroupScopeSequence = 0;

initializeRecentSelectionTracking();

export function capturePageContext(): PageContext {
  const selectedText = resolveSelectedText(
    globalWindow().getSelection?.()?.toString().trim() ?? "",
    getRecentSelectionText()
  );
  const pageText = globalDocument().body?.innerText?.trim() ?? "";
  const metadata = extractJobMetadata();
  const linkedInJobId = extractLinkedInJobId(globalWindow().location.href);
  const canonicalUrl = canonicalizeLinkedInJobUrl(globalWindow().location.href);
  const linkedInDescription = linkedInJobId ? extractLinkedInJobDescriptionFromRoot(globalDocument()) : "";
  const capture = resolveCaptureText({
    selectedText,
    linkedInDescription,
    pageText,
    linkedInJobId
  });

  return {
    url: globalWindow().location.href,
    title: globalDocument().title,
    jobTitle: metadata.jobTitle,
    companyName: metadata.companyName,
    location: metadata.location,
    metadataSource: metadata.source,
    metadataConfidence: metadata.confidence,
    selectedText,
    captureText: capture.text,
    captureSource: capture.source,
    captureExtractor: capture.extractor,
    captureWarnings: capture.warnings,
    rawUrl: globalWindow().location.href,
    canonicalUrl,
    linkedinJobId: linkedInJobId,
    pageTextExcerpt: pageText.slice(0, MAX_TEXT_EXCERPT)
  };
}

export function scanFormFields(): DetectedFormField[] {
  fieldRegistry.clear();
  const pageUrl = globalWindow().location.href;
  const batchId = ++scanBatchSequence;
  const fields: DetectedFormField[] = [];
  const grouped = new Set<string>();
  const candidates = Array.from(
    globalDocument().querySelectorAll('input, textarea, select, button[aria-haspopup="listbox"]') ?? []
  ) as unknown as ScanFieldElement[];

  for (const element of candidates) {
    if (!isVisibleElement(element)) continue;
    const inputType = detectInputType(element);
    if (!inputType) continue;

    if ((inputType === "radio" || inputType === "checkbox") && fieldGroupKey(element, inputType)) {
      const groupKey = fieldGroupKey(element, inputType) as string;
      if (grouped.has(groupKey)) continue;
      grouped.add(groupKey);
      const groupElements = candidates.filter(
        (candidate) => detectInputType(candidate) === inputType && fieldGroupKey(candidate, inputType) === groupKey
      );
      const descriptor = buildDetectedField(groupElements, inputType, pageUrl, batchId, true);
      if (descriptor) {
        fields.push(descriptor.field);
        fieldRegistry.set(descriptor.field.fieldId, descriptor);
      }
      continue;
    }

    const descriptor = buildDetectedField([element], inputType, pageUrl, batchId, false);
    if (descriptor) {
      fields.push(descriptor.field);
      fieldRegistry.set(descriptor.field.fieldId, descriptor);
    }

    if (fields.length >= MAX_FORM_FIELDS) break;
  }

  return fields;
}

export function captureFormFieldAnswer(fieldId: string): CapturedFormAnswer {
  const entry = fieldRegistry.get(fieldId);
  if (!entry) {
    throw new Error("NxJob could not find this field anymore. Rescan the page and retry.");
  }
  if (
    entry.pageUrl !== globalWindow().location.href ||
    entry.elements.some((element) => element.isConnected === false)
  ) {
    throw new Error("NxJob form scan is no longer current. Rescan the page and retry.");
  }
  if (entry.field.inputType === "custom_select" && !entry.reliableLabel) {
    throw new Error("Manually select this custom field before you save an answer.");
  }

  return {
    fieldId,
    answers: captureAnswers(entry)
  };
}

export function resetFormFieldRegistryForTest(): void {
  fieldRegistry.clear();
  fieldSequence = 0;
  scanBatchSequence = 0;
  fieldGroupScopeSequence = 0;
}

function buildDetectedField(
  elements: ScanFieldElement[],
  inputType: DetectedFormField["inputType"],
  pageUrl: string,
  batchId: number,
  isChoiceGroup: boolean
): FieldRegistryEntry | null {
  const primary = elements[0];
  const questionText = isChoiceGroup ? findChoiceGroupQuestionText(primary) : findQuestionText(primary);
  const reliableLabel = Boolean(questionText);

  if (inputType !== "custom_select" && !reliableLabel) return null;

  const field: DetectedFormField = {
    fieldId: createFieldId(inputType, questionText || primary.id || String(fieldSequence + 1), batchId),
    questionText,
    inputType,
    required: elements.some((element) => Boolean(element.required)),
    sensitiveKind: sensitiveKind(questionText, elements),
    recognitionConfidence: reliableLabel ? 0.98 : 0
  };

  return {
    field,
    questionText,
    reliableLabel,
    elements,
    pageUrl,
    batchId
  };
}

function createFieldId(inputType: string, seed: string, batchId: number): string {
  fieldSequence += 1;
  const base = seed
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32) || "field";
  return `nxjob-${inputType}-${batchId}-${base}-${fieldSequence}`;
}

function captureAnswers(entry: FieldRegistryEntry): string[] {
  switch (entry.field.inputType) {
    case "text":
    case "textarea":
      return captureTextAnswer(entry.elements[0]);
    case "radio":
      return entry.elements
        .filter((element) => Boolean(element.checked))
        .map((element) => typeof element.value === "string" ? element.value.trim() : "")
        .filter(Boolean);
    case "checkbox":
      return entry.elements
        .filter((element) => Boolean(element.checked))
        .map((element) => typeof element.value === "string" ? element.value.trim() : "")
        .filter(Boolean);
    case "select":
      return Array.from(entry.elements[0].selectedOptions ?? [])
        .map((option) => compactText(option.text ?? option.value ?? ""))
        .filter(Boolean);
    case "custom_select": {
      const text = compactText(entry.elements[0].textContent ?? "");
      return text ? [text] : [];
    }
  }
}

function captureTextAnswer(element: ScanFieldElement): string[] {
  const rawValue = element.value;
  const value = typeof rawValue === "string" ? rawValue.trim() : "";
  return value ? [value] : [];
}

function detectInputType(element: ScanFieldElement): DetectedFormField["inputType"] | "" {
  const tag = tagNameOf(element);
  if (tag === "textarea") return "textarea";
  if (tag === "select") return "select";
  if (tag === "button" && element.getAttribute("aria-haspopup") === "listbox") return "custom_select";
  if (tag !== "input") return "";

  const type = attr(element, "type").toLowerCase() || "text";
  if (["button", "file", "hidden", "image", "reset", "submit", "password"].includes(type)) return "";
  if (isCredentialField(element)) return "";
  if (type === "radio") return "radio";
  if (type === "checkbox") return "checkbox";
  return "text";
}

function isCredentialField(element: ScanFieldElement): boolean {
  const autocomplete = attr(element, "autocomplete").toLowerCase();
  return ["current-password", "new-password", "username", "one-time-code"].includes(autocomplete);
}

function fieldGroupKey(element: ScanFieldElement, inputType: "radio" | "checkbox"): string | null {
  const name = attr(element, "name");
  if (!name) return null;
  const scope = element.closest("fieldset") ?? element.closest("form") ?? element;
  return `${inputType}:${name}:${fieldGroupScopeId(scope)}`;
}

function fieldGroupScopeId(scope: object): string {
  const existing = fieldGroupScopes.get(scope);
  if (existing) return existing;
  const next = `scope-${++fieldGroupScopeSequence}`;
  fieldGroupScopes.set(scope, next);
  return next;
}

function findQuestionText(element: ScanFieldElement): string {
  const explicit = labelForElement(element);
  if (explicit) return explicit;
  const wrapped = wrappingLabelText(element);
  if (wrapped) return wrapped;
  const legend = fieldsetLegendText(element);
  return legend;
}

function findChoiceGroupQuestionText(element: ScanFieldElement): string {
  return fieldsetLegendText(element);
}

function labelForElement(element: ScanFieldElement): string {
  if (!element.id) return "";
  const label = globalDocument().querySelector(`label[for="${escapeSelector(element.id)}"]`) as ScanFieldElement | null;
  return compactText(label?.textContent ?? "");
}

function wrappingLabelText(element: ScanFieldElement): string {
  const label = element.closest("label");
  if (!label) return "";
  return labelTextWithoutControls(label);
}

function fieldsetLegendText(element: ScanFieldElement): string {
  const fieldset = element.closest("fieldset");
  const legend = fieldset?.querySelector("legend");
  return compactText(legend?.textContent ?? "");
}

function labelTextWithoutControls(label: ScanFieldElement): string {
  const cloned = label.cloneNode?.(true);
  if (!cloned || typeof cloned.querySelectorAll !== "function") {
    return "";
  }
  for (const control of Array.from(cloned.querySelectorAll("input, textarea, select, button"))) {
    if (typeof control.remove === "function") {
      control.remove();
      continue;
    }
    control.parentElement?.removeChild?.(control);
  }
  return compactText(cloned.textContent ?? "");
}

function sensitiveKind(questionText: string, elements: ScanFieldElement[]): string {
  const combined = `${questionText} ${elements.map((element) => `${attr(element, "name")} ${attr(element, "autocomplete")} ${element.id ?? ""}`).join(" ")}`.toLowerCase();
  if (combined.includes("ssn") || combined.includes("social security")) return "ssn";
  if (/(veteran|disability|race|gender|ethnicity|eeo)/.test(combined)) return "eeoc";
  if (combined.includes("salary") || combined.includes("compensation")) return "salary";
  return "";
}

function isVisibleElement(element: ScanFieldElement): boolean {
  const rect = element.getBoundingClientRect();
  const style = globalWindow().getComputedStyle?.(element as unknown as Element) ?? { visibility: "visible", display: "block" };
  return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
}

function initializeRecentSelectionTracking() {
  if (typeof document === "undefined" || typeof window === "undefined") return;

  const captureSelection = () => {
    const text = window.getSelection?.()?.toString().trim() ?? "";
    if (!text) return;
    recentSelectionSnapshot = {
      text,
      href: window.location.href,
      capturedAt: Date.now()
    };
  };

  document.addEventListener?.("selectionchange", captureSelection, true);
  window.addEventListener?.("mouseup", captureSelection, true);
  window.addEventListener?.("keyup", captureSelection, true);
}

function getRecentSelectionText(now = Date.now()): string {
  if (!recentSelectionSnapshot.text) return "";
  if (recentSelectionSnapshot.href !== globalWindow().location.href) return "";
  if (now - recentSelectionSnapshot.capturedAt > RECENT_SELECTION_MAX_AGE_MS) return "";
  return recentSelectionSnapshot.text;
}

function extractJobMetadata(): JobMetadata {
  const host = globalWindow().location.hostname.toLowerCase();
  if (host.includes("linkedin.")) {
    const linkedIn = extractLinkedInJobMetadata();
    if (linkedIn.jobTitle || linkedIn.companyName) return linkedIn;
  }
  const generic = extractGenericJobMetadata();
  if (generic.jobTitle || generic.companyName) return generic;
  return {
    jobTitle: "",
    companyName: "",
    location: "",
    source: "document_title",
    confidence: 0.15
  };
}

function extractLinkedInJobMetadata(): JobMetadata {
  const jobTitle = textFromSelectors([
    ".job-details-jobs-unified-top-card__job-title h1",
    ".job-details-jobs-unified-top-card__job-title",
    ".jobs-unified-top-card__job-title h1",
    ".jobs-unified-top-card__job-title",
    "main h1"
  ]);
  const companyName = textFromSelectors([
    ".job-details-jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    ".jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name"
  ]);
  const location = textFromSelectors([
    ".job-details-jobs-unified-top-card__primary-description-container span",
    ".jobs-unified-top-card__bullet",
    ".jobs-unified-top-card__subtitle-secondary-grouping span"
  ]);
  return {
    jobTitle: stripLinkedInNoise(jobTitle),
    companyName: stripLinkedInNoise(companyName),
    location: stripLinkedInNoise(location),
    source: "linkedin_job_detail",
    confidence: jobTitle && companyName ? 0.9 : 0.55
  };
}

export function extractLinkedInJobId(url: string): string {
  const detailMatch = url.match(/linkedin\.com\/jobs\/view\/(\d+)/i);
  if (detailMatch?.[1]) return detailMatch[1];

  try {
    const parsed = new URL(url);
    if (!/linkedin\.com$/i.test(parsed.hostname) && !/\.linkedin\.com$/i.test(parsed.hostname)) {
      return "";
    }
    return parsed.searchParams.get("currentJobId") ?? "";
  } catch {
    return "";
  }
}

export function canonicalizeLinkedInJobUrl(url: string): string {
  const linkedInJobId = extractLinkedInJobId(url);
  return linkedInJobId ? `https://www.linkedin.com/jobs/view/${linkedInJobId}/` : url;
}

export function extractLinkedInJobDescriptionFromRoot(root: QueryRoot): string {
  const text = textFromSelectors([
    '[componentkey^="JobDetails_AboutTheJob_"]',
    '[data-sdui-component*="aboutTheJob"]',
    ".jobs-description__content .jobs-box__html-content",
    ".jobs-box__html-content#job-details",
    ".jobs-search__job-details--container .jobs-box__html-content",
    ".jobs-search__job-details--container .jobs-description-content__text",
    ".jobs-description-content__text",
    ".jobs-box__html-content",
    "[data-job-description]"
  ], root);
  return cleanLinkedInJobDescriptionText(text).slice(0, MAX_TEXT_EXCERPT);
}

export function cleanLinkedInJobDescriptionText(value: string): string {
  return compactText(value)
    .replace(/^About the job\s*/i, "")
    .replace(/(?:\.\.\.|…)\s*more\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function resolveSelectedText(selectedText: string, cachedSelectedText: string): string {
  return selectedText || cachedSelectedText;
}

export function resolveCaptureText(input: {
  selectedText: string;
  linkedInDescription: string;
  pageText: string;
  linkedInJobId: string;
}): CaptureTextResolution {
  if (input.selectedText.length >= MIN_SELECTED_TEXT_LENGTH) {
    return {
      text: input.selectedText,
      source: "selected_text",
      extractor: "user_selection",
      warnings: []
    };
  }
  if (input.selectedText.length > 0) {
    return {
      text: "",
      source: "selected_text",
      extractor: "user_selection",
      warnings: [`Selected text is shorter than ${MIN_SELECTED_TEXT_LENGTH} characters.`]
    };
  }
  if (input.linkedInJobId && input.linkedInDescription.length >= MIN_AUTO_CAPTURE_TEXT_LENGTH) {
    return {
      text: input.linkedInDescription,
      source: "linkedin_job_detail",
      extractor: "linkedin_auto",
      warnings: []
    };
  }
  if (input.linkedInJobId && input.linkedInDescription) {
    return {
      text: "",
      source: "linkedin_job_detail",
      extractor: "linkedin_auto",
      warnings: [`LinkedIn JD text is shorter than ${MIN_AUTO_CAPTURE_TEXT_LENGTH} characters.`]
    };
  }
  const pageText = compactText(input.pageText).slice(0, MAX_TEXT_EXCERPT);
  if (pageText.length < MIN_AUTO_CAPTURE_TEXT_LENGTH) {
    return {
      text: "",
      source: "page_text_excerpt",
      extractor: "generic_page_excerpt",
      warnings: [`Page excerpt is shorter than ${MIN_AUTO_CAPTURE_TEXT_LENGTH} characters.`]
    };
  }
  return {
    text: pageText,
    source: "page_text_excerpt",
    extractor: "generic_page_excerpt",
    warnings: []
  };
}

function extractGenericJobMetadata(): JobMetadata {
  const jobTitle = textFromSelectors(["[data-job-title]", "[class*='job-title']", "[class*='JobTitle']", "main h1", "h1"]);
  const companyName = textFromSelectors([
    "[data-company-name]",
    "[class*='company-name']",
    "[class*='CompanyName']",
    "[class*='company'] a"
  ]);
  const location = textFromSelectors(["[data-location]", "[class*='location']", "[class*='Location']"]);
  return {
    jobTitle: stripLinkedInNoise(jobTitle),
    companyName: stripLinkedInNoise(companyName),
    location: stripLinkedInNoise(location),
    source: "generic_job_detail",
    confidence: jobTitle ? 0.55 : 0.25
  };
}

function textFromSelectors(selectors: string[], root: QueryRoot = globalDocument()): string {
  for (const selector of selectors) {
    const element = root.querySelector(selector);
    const text = compactText(element?.textContent ?? "");
    if (text) return text;
  }
  return "";
}

function compactText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function stripLinkedInNoise(value: string): string {
  return compactText(value)
    .replace(/\s+with verification$/i, "")
    .replace(/\s+actively hiring.*$/i, "")
    .replace(/\s+promoted.*$/i, "");
}

function tagNameOf(element: ScanFieldElement): string {
  return (element.tagName ?? "").toLowerCase();
}

function attr(element: ScanFieldElement, name: string): string {
  return element.getAttribute(name) ?? "";
}

function globalWindow(): Window & typeof globalThis {
  return window;
}

function globalDocument(): Document {
  return document;
}

function escapeSelector(value: string): string {
  return globalThis.CSS?.escape ? globalThis.CSS.escape(value) : value;
}
