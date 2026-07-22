import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appSource = readFileSync(path.join(__dirname, "../entrypoints/sidepanel/App.tsx"), "utf8");

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

test("FormAnswerResult renders save confirmation inline for the matching pending field", () => {
  const formAnswerResult = sliceBetween(appSource, "function FormAnswerResult", "function SponsorshipResult");

  assert.match(
    formAnswerResult,
    /pendingAnswerSave\?\.jobId === props\.jobId && props\.pendingAnswerSave\.field\.fieldId === row\.field\.fieldId/
  );
  assert.match(formAnswerResult, /Only saved in this browser profile\./);
  assert.match(formAnswerResult, /Confirm Save/);
  assert.match(formAnswerResult, /Cancel/);
});

test("App no longer renders the save confirmation block at the bottom of the sidepanel", () => {
  assert.doesNotMatch(
    appSource,
    /\{pendingAnswerSave\s*\?\s*\(\s*<section className="result-block" aria-label="Save answer confirmation">/
  );
});

for (const { name, fn } of tests) {
  fn();
  console.log(`ok - ${name}`);
}

function sliceBetween(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start);
  assert.notEqual(start, -1, `Missing marker: ${startMarker}`);
  assert.notEqual(end, -1, `Missing marker: ${endMarker}`);
  return source.slice(start, end);
}
