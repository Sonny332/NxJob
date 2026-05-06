import { browser } from "wxt/browser";

export type PageContext = {
  url: string;
  title: string;
  selectedText: string;
  pageTextExcerpt: string;
};

export async function captureActiveTabContext(): Promise<PageContext> {
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });

  if (!tab?.id) {
    throw new Error("No active tab is available.");
  }

  return browser.tabs.sendMessage(tab.id, {
    type: "NXJOB_CAPTURE_PAGE_CONTEXT"
  }) as Promise<PageContext>;
}

