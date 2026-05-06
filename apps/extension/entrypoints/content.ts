import { browser } from "wxt/browser";

import { capturePageContext } from "../src/lib/form-context";

export default defineContentScript({
  matches: ["<all_urls>"],
  main() {
    browser.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message?.type !== "NXJOB_CAPTURE_PAGE_CONTEXT") return false;

      sendResponse(capturePageContext());
      return true;
    });
  }
});

