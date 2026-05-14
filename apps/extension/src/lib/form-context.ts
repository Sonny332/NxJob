export type PageContext = {
  url: string;
  title: string;
  selectedText: string;
  pageTextExcerpt: string;
};

export type FieldContext = {
  fieldId: string;
  label: string;
  placeholder: string;
  surroundingText: string;
  currentValue: string;
  inputType: string;
  required?: boolean;
  options?: string[];
  sensitiveKind?: string;
};

const MAX_TEXT_EXCERPT = 12000;
const MAX_FORM_FIELDS = 30;

export function capturePageContext(): PageContext {
  const selectedText = window.getSelection()?.toString().trim() ?? "";
  const pageText = document.body?.innerText.trim() ?? "";

  return {
    url: window.location.href,
    title: document.title,
    selectedText,
    pageTextExcerpt: pageText.slice(0, MAX_TEXT_EXCERPT)
  };
}

export function captureActiveFieldContext(): FieldContext {
  const element = document.activeElement;
  if (!isFillableElement(element)) {
    throw new Error("Focus a form field first, then retry Fill Form Answer.");
  }

  return {
    fieldId: ensureFieldId(element),
    label: findLabel(element),
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
    placeholder: element.getAttribute("placeholder") ?? "",
    surroundingText: surroundingText(element),
    currentValue: elementValue(element),
    inputType: inputType(element),
    required: element.required,
    options: element instanceof HTMLSelectElement
      ? Array.from(element.options).map((option) => option.text.trim()).filter(Boolean)
      : undefined,
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
  const labelledBy = element.getAttribute("aria-labelledby");
  if (labelledBy) {
    const label = document.getElementById(labelledBy);
    if (label?.textContent?.trim()) return label.textContent.trim();
  }
  return "";
}

function surroundingText(element: Element): string {
  const container = element.closest("section, fieldset, form, div") ?? element.parentElement;
  return container?.textContent?.trim().slice(0, 1000) ?? "";
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
    element.checked = ["true", "yes", "1", "checked"].includes(value.trim().toLowerCase());
  } else {
    setNativeValue(element, value);
  }
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
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

