import { browser } from "wxt/browser";

import type { CapturedFormAnswer, DetectedFormField } from "./form-context";

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

export type FormCaptureBinding = {
  tabId: number;
  url: string;
};

let activeFormCaptureBinding: FormCaptureBinding | null = null;

export async function captureActiveTabContext(): Promise<PageContext> {
  const tab = await getActiveTab();
  return sendMessageWithContentScriptFallback<PageContext>(tab.id, {
    type: "NXJOB_CAPTURE_PAGE_CONTEXT"
  });
}

export async function scanActiveTabFormFields(): Promise<DetectedFormField[]> {
  const tab = await getActiveTab();
  activeFormCaptureBinding = null;
  const fields = await sendMessageWithContentScriptFallback<DetectedFormField[]>(tab.id, {
    type: "NXJOB_SCAN_FORM_FIELDS"
  });
  activeFormCaptureBinding = { tabId: tab.id, url: tab.url ?? "" };
  return fields;
}

export async function captureFormFieldAnswer(fieldId: string): Promise<CapturedFormAnswer> {
  const tab = await getActiveTab();
  assertFormCaptureBinding(activeFormCaptureBinding, tab);
  return sendMessageWithContentScriptFallback<CapturedFormAnswer>(tab.id, {
    type: "NXJOB_CAPTURE_FORM_FIELD_ANSWER",
    fieldId
  });
}

export function assertFormCaptureBinding(
  binding: FormCaptureBinding | null,
  tab: { id: number; url?: string }
): asserts binding is FormCaptureBinding {
  if (!binding || binding.tabId !== tab.id || binding.url !== (tab.url ?? "")) {
    throw new Error("NxJob form scan is no longer current. Rescan the page and retry.");
  }
}

export async function listOpenTabUrls(): Promise<string[]> {
  const tabs = await browser.tabs.query({});
  return tabs.map((tab) => tab.url ?? "").filter((url) => url && !isRestrictedUrl(url));
}

async function getActiveTab(): Promise<{ id: number; url?: string }> {
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });

  if (!tab?.id) {
    throw new Error("No active tab is available.");
  }

  if (tab.url && isRestrictedUrl(tab.url)) {
    throw new Error("NxJob cannot read this browser page. Open a job posting page, then retry.");
  }

  return { id: tab.id, url: tab.url };
}

async function sendMessageWithContentScriptFallback<T>(
  tabId: number,
  message: Record<string, unknown>
): Promise<T> {
  try {
    return await browser.tabs.sendMessage(tabId, message) as T;
  } catch (error) {
    if (!isMissingReceiverError(error)) {
      throw error;
    }
  }

  try {
    await browser.scripting.executeScript({
      target: { tabId },
      files: ["/content-scripts/content.js"]
    });
    return await browser.tabs.sendMessage(tabId, message) as T;
  } catch (error) {
    if (isMissingReceiverError(error)) {
      throw new Error("NxJob cannot connect to this page yet. Reload the job page, select the JD again, then retry.");
    }
    throw error;
  }
}

function isMissingReceiverError(error: unknown): boolean {
  return error instanceof Error && error.message.includes("Receiving end does not exist");
}

function isRestrictedUrl(url: string): boolean {
  return (
    url.startsWith("chrome://") ||
    url.startsWith("edge://") ||
    url.startsWith("about:") ||
    url.startsWith("chrome-extension://")
  );
}

