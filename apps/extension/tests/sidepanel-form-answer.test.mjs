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
  assert.match(formAnswerResult, /Only saved to Local Service on this device\./);
  assert.match(formAnswerResult, /Confirm Save/);
  assert.match(formAnswerResult, /Cancel/);
});

test("App no longer renders the save confirmation block at the bottom of the sidepanel", () => {
  assert.doesNotMatch(
    appSource,
    /\{pendingAnswerSave\s*\?\s*\(\s*<section className="result-block" aria-label="Save answer confirmation">/
  );
});

test("runFormAnswer refreshes service-backed answers before matching and clears stale candidates on failure", () => {
  const appBody = sliceBetween(appSource, "async function runFormAnswer", "async function handleMasterResumeFile");

  assert.match(appBody, /const answerLibrary = await refreshSavedAnswers\(\{ rethrowUnavailable: false, notifyUnavailable: false \}\);/);
  assert.match(appBody, /await refreshFormAnswerMatches\(job\.id, fields, answerLibrary\.answers\);/);
  assert.match(appBody, /clearFormAnswerMatches\(job\.id\);/);
  assert.doesNotMatch(appBody, /refreshFormAnswerMatches\(job\.id, fields, savedAnswers\)/);
});

test("offline answer-library state keeps scan enabled but disables candidate and saved-answer actions with recovery text", () => {
  const jobDetail = sliceBetween(appSource, "function JobDetail", "function FormAnswerResult");
  const formAnswerResult = sliceBetween(appSource, "function FormAnswerResult", "function SponsorshipResult");

  assert.match(jobDetail, /disabled=\{job\.workflows\.formAnswer\.status === "running"\}/);
  assert.match(appSource, /const ANSWER_LIBRARY_RECOVERY_TEXT = "Start Local Service to use saved answers\.";/);
  assert.match(formAnswerResult, /props\.answerLibraryMessage/);
  assert.match(formAnswerResult, /disabled=\{!props\.answerLibraryAvailable\}/);
  assert.match(formAnswerResult, /onClick=\{\(\) => props\.onSaveAnswer\(row\.field\)\}/);
  assert.match(formAnswerResult, /Save this answer/);
});

test("answer-library handlers guard again before copy save edit delete and clear", () => {
  const functionsToCheck = [
    "async function copySavedAnswer",
    "async function startSaveAnswer",
    "async function confirmSaveAnswer",
    "async function saveEditedAnswer",
    "async function removeSavedAnswer",
    "async function clearAllSavedAnswers"
  ];

  for (const marker of functionsToCheck) {
    const fnBody = sliceBetween(appSource, marker, "\n\n  ");
    assert.match(fnBody, /if \(!requireAnswerLibraryActionAvailable\(\)\) return;/, marker);
  }
});

test("answer-library operation failures funnel through the unified unavailable handler", () => {
  const appBody = sliceBetween(appSource, "export function App()", "function DolIndexSettings");

  assert.match(appBody, /function handleAnswerLibraryUnavailable\(\)\s*\{\s*markAnswerLibraryUnavailable\(\);\s*setMessage\(ANSWER_LIBRARY_RECOVERY_TEXT\);/s);
  assert.match(appBody, /if \(isSavedAnswersUnavailableError\(error\)\) \{\s*handleAnswerLibraryUnavailable\(\);\s*return;\s*\}/s);

  for (const marker of [
    "async function copySavedAnswer",
    "async function confirmSaveAnswer",
    "async function saveEditedAnswer",
    "async function removeSavedAnswer",
    "async function clearAllSavedAnswers"
  ]) {
    const fnBody = sliceBetween(appSource, marker, "\n\n  ");
    assert.match(fnBody, /handleAnswerLibraryOperationError\(/, marker);
  }
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
