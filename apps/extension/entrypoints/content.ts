import { browser } from "wxt/browser";

import {
  captureFormFieldAnswer,
  capturePageContext,
  scanFormFields
} from "../src/lib/form-context";

export default defineContentScript({
  matches: ["<all_urls>"],
  main() {
    browser.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message?.type === "NXJOB_SCAN_FORM_FIELDS") {
        sendResponse(scanFormFields());
        return true;
      }

      if (message?.type === "NXJOB_CAPTURE_FORM_FIELD_ANSWER") {
        sendResponse(captureFormFieldAnswer(message.fieldId ?? ""));
        return true;
      }

      if (message?.type !== "NXJOB_CAPTURE_PAGE_CONTEXT") return false;

      sendResponse(capturePageContext());
      return true;
    });
  }
});

