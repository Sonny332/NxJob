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

export type FieldContext = {
  fieldId: string;
  label: string;
  questionText?: string;
  placeholder: string;
  surroundingText: string;
  currentValue: string;
  inputType: string;
  required?: boolean;
  options?: string[];
  sensitiveKind?: string;
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

let recentSelectionSnapshot: RecentSelectionSnapshot = {
  text: "",
  href: "",
  capturedAt: 0
};

initializeRecentSelectionTracking();

export function capturePageContext(): PageContext {
  const selectedText = resolveSelectedText(
    window.getSelection()?.toString().trim() ?? "",
    getRecentSelectionText()
  );
  const pageText = document.body?.innerText.trim() ?? "";
  const metadata = extractJobMetadata();
  const linkedInJobId = extractLinkedInJobId(window.location.href);
  const canonicalUrl = canonicalizeLinkedInJobUrl(window.location.href);
  const linkedInDescription = linkedInJobId ? extractLinkedInJobDescriptionFromRoot(document) : "";
  const capture = resolveCaptureText({
    selectedText,
    linkedInDescription,
    pageText,
    linkedInJobId,
  });

  return {
    url: window.location.href,
    title: document.title,
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
    rawUrl: window.location.href,
    canonicalUrl,
    linkedinJobId: linkedInJobId,
    pageTextExcerpt: pageText.slice(0, MAX_TEXT_EXCERPT)
  };
}

function initializeRecentSelectionTracking() {
  if (typeof document === "undefined" || typeof window === "undefined") return;

  const captureSelection = () => {
    const text = window.getSelection()?.toString().trim() ?? "";
    if (!text) return;
    recentSelectionSnapshot = {
      text,
      href: window.location.href,
      capturedAt: Date.now()
    };
  };

  document.addEventListener("selectionchange", captureSelection, true);
  window.addEventListener("mouseup", captureSelection, true);
  window.addEventListener("keyup", captureSelection, true);
}

function getRecentSelectionText(now = Date.now()): string {
  if (!recentSelectionSnapshot.text) return "";
  if (recentSelectionSnapshot.href !== window.location.href) return "";
  if (now - recentSelectionSnapshot.capturedAt > RECENT_SELECTION_MAX_AGE_MS) return "";
  return recentSelectionSnapshot.text;
}

export function captureActiveFieldContext(): FieldContext {
  const element = document.activeElement;
  if (!isFillableElement(element)) {
    throw new Error("Focus a form field first, then retry Fill Form Answer.");
  }

  return {
    fieldId: ensureFieldId(element),
    label: findLabel(element),
    questionText: findQuestionText(element),
    placeholder: element.getAttribute("placeholder") ?? "",
    surroundingText: surroundingText(element),
    currentValue: element.value,
    inputType: element.getAttribute("type") ?? element.tagName.toLowerCase(),
    required: element.required,
    sensitiveKind: sensitiveKind(element)
  };
}

export function scanFormFields(): { fields: FieldContext[]; url: string; title: string } {
  const fields = Array.from(document.querySelectorAll("input, textarea, select"))
    .filter(isSupportedFormElement)
    .filter(isVisibleElement)
    .slice(0, MAX_FORM_FIELDS)
    .map(fieldContextFromElement);

  return {
    fields,
    url: window.location.href,
    title: document.title
  };
}

export function fillActiveField(value: string): { filled: boolean } {
  const element = document.activeElement;
  if (!isFillableElement(element)) {
    throw new Error("Focus a form field first, then confirm again.");
  }
  setNativeValue(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
  return { filled: true };
}

export function fillFieldById(fieldId: string, value: string): { filled: boolean } {
  const element = document.querySelector(`[data-nxjob-field-id="${CSS.escape(fieldId)}"]`);
  if (!isSupportedFormElement(element)) {
    throw new Error("NxJob could not find this form field anymore. Rescan the page and retry.");
  }
  setElementValue(element, value);
  return { filled: true };
}

function fieldContextFromElement(element: SupportedFormElement): FieldContext {
  return {
    fieldId: ensureFieldId(element),
    label: findLabel(element),
    questionText: findQuestionText(element),
    placeholder: element.getAttribute("placeholder") ?? "",
    surroundingText: surroundingText(element),
    currentValue: elementValue(element),
    inputType: inputType(element),
    required: element.required,
    options: fieldOptions(element),
    sensitiveKind: sensitiveKind(element)
  };
}

type SupportedFormElement = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

function isFillableElement(element: Element | null): element is HTMLInputElement | HTMLTextAreaElement {
  if (!element) return false;
  if (element instanceof HTMLTextAreaElement) return true;
  if (!(element instanceof HTMLInputElement)) return false;
  const type = (element.getAttribute("type") ?? "text").toLowerCase();
  return !["button", "checkbox", "file", "hidden", "image", "radio", "reset", "submit"].includes(type);
}

function isSupportedFormElement(element: Element | null): element is SupportedFormElement {
  if (!element) return false;
  if (element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) return true;
  if (!(element instanceof HTMLInputElement)) return false;
  const type = (element.getAttribute("type") ?? "text").toLowerCase();
  return !["button", "file", "hidden", "image", "reset", "submit"].includes(type);
}

function findLabel(element: SupportedFormElement): string {
  if (element.id) {
    const label = document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
    if (label?.textContent?.trim()) return label.textContent.trim();
  }
  const wrappingLabel = element.closest("label");
  if (wrappingLabel?.textContent?.trim()) return wrappingLabel.textContent.trim();
  const ariaLabel = element.getAttribute("aria-label");
  if (ariaLabel) return ariaLabel;
  const labelled = textFromIdRefs(element.getAttribute("aria-labelledby"));
  if (labelled) return labelled;
  return "";
}

function findQuestionText(element: SupportedFormElement): string {
  const labelled = findLabel(element);
  const legend = element.closest("fieldset")?.querySelector("legend")?.textContent?.trim() ?? "";
  const heading = closestHeadingText(element);
  const placeholder = element.getAttribute("placeholder")?.trim() ?? "";
  const describedBy = textFromIdRefs(element.getAttribute("aria-describedby"));
  const localText = localFieldText(element);
  return firstUsefulText([legend, labelled, heading, describedBy, placeholder, localText]);
}

function closestHeadingText(element: Element): string {
  let current: Element | null = element.parentElement;
  for (let depth = 0; current && depth < 5; depth += 1) {
    const heading = current.querySelector("h1,h2,h3,h4,h5,h6,[role='heading']");
    if (heading?.textContent?.trim()) return heading.textContent.trim();
    current = current.parentElement;
  }
  return "";
}

function firstUsefulText(values: string[]): string {
  for (const value of values) {
    const clean = compactText(value);
    if (clean && clean.length <= 300) return clean;
  }
  return "";
}

function surroundingText(element: Element): string {
  const container = nearestTextContainer(element);
  return compactText(container?.textContent ?? "").slice(0, 400);
}

function localFieldText(element: Element): string {
  const values = [
    textFromIdRefs((element as HTMLElement).getAttribute("aria-describedby")),
    compactText(element.parentElement?.textContent ?? ""),
    compactText(nearestTextContainer(element)?.textContent ?? "")
  ];
  for (const value of values) {
    if (value && value.length <= 220) return value;
  }
  return "";
}

function nearestTextContainer(element: Element): Element | null {
  const selectors = [
    "fieldset",
    "[role='group']",
    "[role='radiogroup']",
    "[role='row']",
    "li",
    "td",
    "tr",
    "section",
    "article",
    "div"
  ];
  let current: Element | null = element.parentElement;
  for (let depth = 0; current && depth < 5; depth += 1) {
    if (!current.matches("form, body")) {
      const text = compactText(current.textContent ?? "");
      if (text && text.length <= 400 && selectors.some((selector) => current?.matches(selector))) {
        return current;
      }
    }
    current = current.parentElement;
  }
  return element.parentElement;
}

function textFromIdRefs(value: string | null): string {
  if (!value) return "";
  const parts = value
    .split(/\s+/)
    .map((id) => document.getElementById(id))
    .filter((node): node is HTMLElement => Boolean(node))
    .map((node) => compactText(node.textContent ?? ""))
    .filter(Boolean);
  return parts.join(" ").slice(0, 300);
}

function setNativeValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = element instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
  descriptor?.set?.call(element, value);
}

function setElementValue(element: SupportedFormElement, value: string) {
  if (element instanceof HTMLSelectElement) {
    const matched = Array.from(element.options).find(
      (option) => option.value === value || option.text.trim().toLowerCase() === value.trim().toLowerCase()
    );
    element.value = matched?.value ?? value;
  } else if (element instanceof HTMLInputElement && ["checkbox", "radio"].includes(inputType(element))) {
    const matched = matchingChoiceElement(element, value);
    if (matched) {
      matched.checked = true;
      matched.dispatchEvent(new Event("input", { bubbles: true }));
      matched.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
    element.checked = ["true", "yes", "1", "checked"].includes(value.trim().toLowerCase());
  } else {
    setNativeValue(element, value);
  }
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

function matchingChoiceElement(element: HTMLInputElement, value: string): HTMLInputElement | null {
  const name = element.getAttribute("name");
  const candidates = name
    ? Array.from(document.querySelectorAll(`input[name="${CSS.escape(name)}"]`))
    : [element];
  const expected = compactText(value).toLowerCase();
  for (const candidate of candidates) {
    if (!(candidate instanceof HTMLInputElement)) continue;
    const label = compactText(findLabel(candidate)).toLowerCase();
    const candidateValue = compactText(candidate.value).toLowerCase();
    if (expected && (label === expected || candidateValue === expected)) return candidate;
  }
  return null;
}

function elementValue(element: SupportedFormElement): string {
  if (element instanceof HTMLInputElement && ["checkbox", "radio"].includes(inputType(element))) {
    return element.checked ? "checked" : "";
  }
  return element.value;
}

function inputType(element: SupportedFormElement): string {
  if (element instanceof HTMLSelectElement) return "select";
  return element.getAttribute("type") ?? element.tagName.toLowerCase();
}

function fieldOptions(element: SupportedFormElement): string[] | undefined {
  if (element instanceof HTMLSelectElement) {
    return Array.from(element.options).map((option) => option.text.trim()).filter(Boolean);
  }
  if (element instanceof HTMLInputElement && ["radio", "checkbox"].includes(inputType(element))) {
    const name = element.getAttribute("name");
    if (name) {
      const peers = Array.from(document.querySelectorAll(`input[name="${CSS.escape(name)}"]`))
        .filter((peer): peer is HTMLInputElement => peer instanceof HTMLInputElement)
        .filter((peer) => inputType(peer) === inputType(element));
      const labels = peers.map((peer) => findLabel(peer) || peer.value).map(compactText).filter(Boolean);
      return Array.from(new Set(labels));
    }
    const label = findLabel(element) || element.value;
    return label ? [label] : undefined;
  }
  return undefined;
}

function isVisibleElement(element: SupportedFormElement): boolean {
  const rect = element.getBoundingClientRect();
  const style = window.getComputedStyle(element);
  return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
}

function ensureFieldId(element: SupportedFormElement): string {
  const existing = element.getAttribute("data-nxjob-field-id");
  if (existing) return existing;
  const id = `nxjob-field-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  element.setAttribute("data-nxjob-field-id", id);
  return id;
}

function sensitiveKind(element: SupportedFormElement): string {
  const text = `${findLabel(element)} ${element.getAttribute("name") ?? ""} ${element.id} ${element.getAttribute("autocomplete") ?? ""}`.toLowerCase();
  if (text.includes("ssn") || text.includes("social security")) return "ssn";
  if (text.includes("disability") || text.includes("veteran") || text.includes("race") || text.includes("gender")) {
    return "eeoc";
  }
  if (text.includes("password")) return "password";
  return "";
}

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

function extractJobMetadata(): JobMetadata {
  const host = window.location.hostname.toLowerCase();
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
    .replace(/(?:\.\.\.|\u2026)\s*more\b/gi, "")
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

function textFromSelectors(selectors: string[], root: QueryRoot = document): string {
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
