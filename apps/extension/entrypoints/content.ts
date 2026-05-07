import { browser } from "wxt/browser";

import { captureActiveFieldContext, capturePageContext, fillActiveField } from "../src/lib/form-context";

export default defineContentScript({
  matches: ["<all_urls>"],
  main() {
    browser.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message?.type === "NXJOB_CAPTURE_ACTIVE_FIELD_CONTEXT") {
        sendResponse(captureActiveFieldContext());
        return true;
      }

      if (message?.type === "NXJOB_FILL_ACTIVE_FIELD") {
        sendResponse(fillActiveField(message.value ?? ""));
        return true;
      }

      if (message?.type !== "NXJOB_CAPTURE_PAGE_CONTEXT") return false;

      sendResponse(capturePageContext());
      return true;
    });
  }
});

