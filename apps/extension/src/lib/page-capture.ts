import { browser } from "wxt/browser";

import type { FieldContext } from "./form-context";

export type PageContext = {
  url: string;
  title: string;
  selectedText: string;
  pageTextExcerpt: string;
};

export async function captureActiveTabContext(): Promise<PageContext> {
  const tab = await getActiveTab();
  return sendMessageWithContentScriptFallback<PageContext>(tab.id, {
    type: "NXJOB_CAPTURE_PAGE_CONTEXT"
  });
}

export async function captureActiveFieldContext(): Promise<FieldContext> {
  const tab = await getActiveTab();
  return sendMessageWithContentScriptFallback<FieldContext>(tab.id, {
    type: "NXJOB_CAPTURE_ACTIVE_FIELD_CONTEXT"
  });
}

export async function fillActiveField(value: string): Promise<{ filled: boolean }> {
  const tab = await getActiveTab();
  return sendMessageWithContentScriptFallback<{ filled: boolean }>(tab.id, {
    type: "NXJOB_FILL_ACTIVE_FIELD",
    value
  });
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

