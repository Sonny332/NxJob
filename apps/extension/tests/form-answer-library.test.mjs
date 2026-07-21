import assert from "node:assert/strict";

import {
  __resetFormAnswerLibraryForTest,
  clearSavedAnswers,
  copyAnswerAndTouch,
  deleteSavedAnswer,
  findAnswerCandidates,
  loadSavedAnswers,
  saveConfirmedAnswer,
  touchSavedAnswer,
  updateSavedAnswer
} from "../src/lib/form-answer-library.ts";

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

async function run() {
  for (const { name, fn } of tests) {
    await __resetFormAnswerLibraryForTest();
    await fn();
    console.log(`ok - ${name}`);
  }
}

test("exact normalized question match wins over lexical alternatives", async () => {
  await saveConfirmedAnswer({
    question: "Are you legally authorized to work in the United States?",
    fieldType: "radio",
    answers: ["Yes"],
    sensitive: false
  });
  await saveConfirmedAnswer({
    question: "Will you now or in the future require visa sponsorship?",
    fieldType: "radio",
    answers: ["No"],
    sensitive: false
  });

  const matches = await findAnswerCandidates({
    questionText: "Are you legally authorized to work in the United States?",
    inputType: "radio",
    required: true,
    sensitiveKind: "",
    recognitionConfidence: 0.98,
    fieldId: "field-1"
  });

  assert.equal(matches.length, 1);
  assert.equal(matches[0].answer.answers[0], "Yes");
  assert.equal(matches[0].confidenceLabel, "High");
});

test("country, negation, and time qualifier mismatches block reuse", async () => {
  await saveConfirmedAnswer({
    question: "Are you legally authorized to work in the United States?",
    fieldType: "radio",
    answers: ["Yes"],
    sensitive: false
  });
  await saveConfirmedAnswer({
    question: "Will you now or in the future require visa sponsorship?",
    fieldType: "radio",
    answers: ["No"],
    sensitive: false
  });
  await saveConfirmedAnswer({
    question: "When can you start?",
    fieldType: "text",
    answers: ["Two weeks"],
    sensitive: false
  });

  assert.equal(
    (
      await findAnswerCandidates({
        questionText: "Are you legally authorized to work in Canada?",
        inputType: "radio",
        required: true,
        sensitiveKind: "",
        recognitionConfidence: 0.95,
        fieldId: "field-2"
      })
    ).length,
    0
  );
  assert.equal(
    (
      await findAnswerCandidates({
        questionText: "Will you require visa sponsorship?",
        inputType: "radio",
        required: true,
        sensitiveKind: "",
        recognitionConfidence: 0.95,
        fieldId: "field-3"
      })
    ).length,
    0
  );
  assert.equal(
    (
      await findAnswerCandidates({
        questionText: "How soon could you start?",
        inputType: "text",
        required: true,
        sensitiveKind: "",
        recognitionConfidence: 0.95,
        fieldId: "field-4"
      })
    ).length,
    0
  );
});

test("non-exact generic, country, and EEO questions never reuse a different qualifier", async () => {
  await saveConfirmedAnswer({
    question: "First legal name",
    fieldType: "text",
    answers: ["Ada"],
    sensitive: false
  });
  await saveConfirmedAnswer({
    question: "Are you legally authorized to work in France?",
    fieldType: "radio",
    answers: ["Yes"],
    sensitive: false
  });
  await saveConfirmedAnswer({
    question: "Voluntary self-identification of disability status",
    fieldType: "radio",
    answers: ["No"],
    sensitive: true
  });

  const firstToLast = await findAnswerCandidates({
    questionText: "Last legal name",
    inputType: "text",
    required: true,
    sensitiveKind: "",
    recognitionConfidence: 0.98,
    fieldId: "name-field"
  });
  const franceToGermany = await findAnswerCandidates({
    questionText: "Are you legally authorized to work in Germany?",
    inputType: "radio",
    required: true,
    sensitiveKind: "",
    recognitionConfidence: 0.98,
    fieldId: "country-field"
  });
  const disabilityToVeteran = await findAnswerCandidates({
    questionText: "Voluntary self-identification of veteran status",
    inputType: "radio",
    required: true,
    sensitiveKind: "eeoc",
    recognitionConfidence: 0.98,
    fieldId: "eeo-field"
  });

  assert.deepEqual(firstToLast, []);
  assert.deepEqual(franceToGermany, []);
  assert.deepEqual(disabilityToVeteran, []);
});

test("work authorization does not reuse a non-exact answer across unlisted country expressions", async () => {
  await saveConfirmedAnswer({
    question: "Are you legally authorized to work in Japan?",
    fieldType: "radio",
    answers: ["Yes"],
    sensitive: false
  });

  const matches = await findAnswerCandidates({
    questionText: "Are you legally authorized to work in Brazil?",
    inputType: "radio",
    required: true,
    sensitiveKind: "",
    recognitionConfidence: 0.98,
    fieldId: "japan-brazil-work-authorization"
  });

  assert.deepEqual(matches, []);
});

test("matching returns top three sorted by score then recency", async () => {
  await saveConfirmedAnswer({
    question: "Please share your LinkedIn profile URL",
    fieldType: "text",
    answers: ["https://linkedin.example/a"],
    sensitive: false
  });
  const second = await saveConfirmedAnswer({
    question: "LinkedIn URL",
    fieldType: "text",
    answers: ["https://linkedin.example/b"],
    sensitive: false
  });
  const third = await saveConfirmedAnswer({
    question: "LinkedIn profile",
    fieldType: "text",
    answers: ["https://linkedin.example/c"],
    sensitive: false
  });
  await saveConfirmedAnswer({
    question: "Portfolio website",
    fieldType: "text",
    answers: ["https://portfolio.example"],
    sensitive: false
  });
  await touchSavedAnswer(second.id);
  await touchSavedAnswer(third.id);

  const matches = await findAnswerCandidates({
    questionText: "LinkedIn profile URL",
    inputType: "text",
    required: false,
    sensitiveKind: "",
    recognitionConfidence: 0.92,
    fieldId: "field-5"
  });

  assert.equal(matches.length, 3);
  assert.ok(matches[0].score >= matches[1].score);
  assert.ok(matches[1].score >= matches[2].score);
  assert.equal(matches[0].answer.answers[0], "https://linkedin.example/a");
  assert.deepEqual(
    matches.slice(1).map((item) => item.answer.answers[0]),
    ["https://linkedin.example/c", "https://linkedin.example/b"]
  );
  assert.ok(matches.every((item) => item.score >= 0.6));
});

test("saving exact same normalized question type and answers deduplicates and updates recency", async () => {
  const first = await saveConfirmedAnswer({
    question: "What is your current salary?",
    fieldType: "text",
    answers: ["100000"],
    sensitive: true
  });
  const second = await saveConfirmedAnswer({
    question: "What is your CURRENT salary ?",
    fieldType: "text",
    answers: ["100000"],
    sensitive: true
  });

  const records = await loadSavedAnswers();
  assert.equal(records.length, 1);
  assert.equal(first.id, second.id);
  assert.equal(records[0].answers[0], "100000");
  assert.ok(Date.parse(records[0].lastUsedAt) >= Date.parse(records[0].createdAt));
});

test("edit delete and clear operate on only the answer library storage key", async () => {
  const saved = await saveConfirmedAnswer({
    question: "Website",
    fieldType: "text",
    answers: ["https://old.example"],
    sensitive: false
  });

  await updateSavedAnswer(saved.id, ["https://new.example"]);
  let records = await loadSavedAnswers();
  assert.deepEqual(records[0].answers, ["https://new.example"]);

  await deleteSavedAnswer(saved.id);
  records = await loadSavedAnswers();
  assert.equal(records.length, 0);

  await saveConfirmedAnswer({
    question: "Are you willing to relocate?",
    fieldType: "radio",
    answers: ["Yes"],
    sensitive: false
  });
  await clearSavedAnswers();
  assert.deepEqual(await loadSavedAnswers(), []);
});

test("clipboard failure does not update answer recency", async () => {
  const saved = await saveConfirmedAnswer({
    question: "Portfolio website",
    fieldType: "text",
    answers: ["https://portfolio.example"],
    sensitive: false
  });
  const before = (await loadSavedAnswers())[0].lastUsedAt;

  await assert.rejects(
    copyAnswerAndTouch(saved.id, saved.answers[0], async () => {
      throw new Error("Clipboard permission denied");
    }),
    /Clipboard permission denied/
  );

  assert.equal((await loadSavedAnswers())[0].lastUsedAt, before);
});

run();
