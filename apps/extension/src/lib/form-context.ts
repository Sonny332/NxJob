export type PageContext = {
  url: string;
  title: string;
  selectedText: string;
  pageTextExcerpt: string;
};

export type FieldContext = {
  label: string;
  placeholder: string;
  surroundingText: string;
  currentValue: string;
  inputType: string;
};

const MAX_TEXT_EXCERPT = 12000;

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
    label: findLabel(element),
    placeholder: element.getAttribute("placeholder") ?? "",
    surroundingText: surroundingText(element),
    currentValue: element.value,
    inputType: element.getAttribute("type") ?? element.tagName.toLowerCase()
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

function isFillableElement(element: Element | null): element is HTMLInputElement | HTMLTextAreaElement {
  if (!element) return false;
  if (element instanceof HTMLTextAreaElement) return true;
  if (!(element instanceof HTMLInputElement)) return false;
  const type = (element.getAttribute("type") ?? "text").toLowerCase();
  return !["button", "checkbox", "file", "hidden", "image", "radio", "reset", "submit"].includes(type);
}

function findLabel(element: HTMLInputElement | HTMLTextAreaElement): string {
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

