import assert from "node:assert/strict";

import {
  __resetFormAnswerLibraryForTest,
  __setFormAnswerLibraryTestHooks,
  clearSavedAnswers,
  copyAnswerAndTouch,
  deleteSavedAnswer,
  findAnswerCandidates,
  loadSavedAnswers,
  applyRefreshedTrackedAnswerCandidates,
  refreshAnswerCandidateRows,
  runAnswerLibraryMutationAndRefreshCandidates,
  saveConfirmedAnswer,
  touchSavedAnswer,
  updateSavedAnswer
} from "../src/lib/form-answer-library.ts";

const STORAGE_KEY = "nxjob.form-answer-library.v1";
const MARKER_KEY = "nxjob.form-answer-library.service-imported.v1";
const OFFLINE_MESSAGE = "Local Service is unavailable. Start it to use saved answers.";

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
  const matches = findAnswerCandidates(
    {
      questionText: "Are you legally authorized to work in the United States?",
      inputType: "radio",
      required: true,
      sensitiveKind: "",
      recognitionConfidence: 0.98,
      fieldId: "field-1"
    },
    [
      createSavedAnswerRecord("Are you legally authorized to work in the United States?", "radio", ["Yes"]),
      createSavedAnswerRecord("Will you now or in the future require visa sponsorship?", "radio", ["No"])
    ]
  );

  assert.equal(matches.length, 1);
  assert.equal(matches[0].answer.answers[0], "Yes");
  assert.equal(matches[0].confidenceLabel, "High");
});

test("country, negation, and time qualifier mismatches block reuse", async () => {
  const answers = [
    createSavedAnswerRecord("Are you legally authorized to work in the United States?", "radio", ["Yes"]),
    createSavedAnswerRecord("Will you now or in the future require visa sponsorship?", "radio", ["No"]),
    createSavedAnswerRecord("When can you start?", "text", ["Two weeks"])
  ];

  assert.equal(
    findAnswerCandidates(
      {
        questionText: "Are you legally authorized to work in Canada?",
        inputType: "radio",
        required: true,
        sensitiveKind: "",
        recognitionConfidence: 0.95,
        fieldId: "field-2"
      },
      answers
    ).length,
    0
  );
  assert.equal(
    findAnswerCandidates(
      {
        questionText: "Will you require visa sponsorship?",
        inputType: "radio",
        required: true,
        sensitiveKind: "",
        recognitionConfidence: 0.95,
        fieldId: "field-3"
      },
      answers
    ).length,
    0
  );
  assert.equal(
    findAnswerCandidates(
      {
        questionText: "How soon could you start?",
        inputType: "text",
        required: true,
        sensitiveKind: "",
        recognitionConfidence: 0.95,
        fieldId: "field-4"
      },
      answers
    ).length,
    0
  );
});

test("non-exact generic, country, and EEO questions never reuse a different qualifier", async () => {
  const answers = [
    createSavedAnswerRecord("First legal name", "text", ["Ada"]),
    createSavedAnswerRecord("Are you legally authorized to work in France?", "radio", ["Yes"]),
    createSavedAnswerRecord("Voluntary self-identification of disability status", "radio", ["No"], true)
  ];

  assert.deepEqual(
    findAnswerCandidates(
      {
        questionText: "Last legal name",
        inputType: "text",
        required: true,
        sensitiveKind: "",
        recognitionConfidence: 0.98,
        fieldId: "name-field"
      },
      answers
    ),
    []
  );
  assert.deepEqual(
    findAnswerCandidates(
      {
        questionText: "Are you legally authorized to work in Germany?",
        inputType: "radio",
        required: true,
        sensitiveKind: "",
        recognitionConfidence: 0.98,
        fieldId: "country-field"
      },
      answers
    ),
    []
  );
  assert.deepEqual(
    findAnswerCandidates(
      {
        questionText: "Voluntary self-identification of veteran status",
        inputType: "radio",
        required: true,
        sensitiveKind: "eeoc",
        recognitionConfidence: 0.98,
        fieldId: "eeo-field"
      },
      answers
    ),
    []
  );
});

test("matching returns top three sorted by score then recency", async () => {
  const matches = findAnswerCandidates(
    {
      questionText: "LinkedIn profile URL",
      inputType: "text",
      required: false,
      sensitiveKind: "",
      recognitionConfidence: 0.92,
      fieldId: "field-5"
    },
    [
      createSavedAnswerRecord("Please share your LinkedIn profile URL", "text", ["https://linkedin.example/a"], false, "2026-07-01T00:00:00Z"),
      createSavedAnswerRecord("LinkedIn URL", "text", ["https://linkedin.example/b"], false, "2026-07-02T00:00:00Z"),
      createSavedAnswerRecord("LinkedIn profile", "text", ["https://linkedin.example/c"], false, "2026-07-03T00:00:00Z"),
      createSavedAnswerRecord("Portfolio website", "text", ["https://portfolio.example"], false, "2026-07-04T00:00:00Z")
    ]
  );

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

test("browser answers import once into service and write the marker after success", async () => {
  const storage = createStorageSpy({
    [STORAGE_KEY]: {
      version: 1,
      answers: [createSavedAnswerRecord("What is your current salary?", "text", ["100000"], true)]
    }
  });
  const service = createServiceStub();
  __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });

  const answers = await loadSavedAnswers();

  assert.equal(service.calls.imports.length, 1);
  assert.equal(service.calls.imports[0].answers.length, 1);
  assert.equal(service.calls.imports[0].answers[0].answers[0], "100000");
  assert.equal(answers.length, 1);
  assert.deepEqual(storage.calls.get, [MARKER_KEY, STORAGE_KEY]);
  assert.equal(storage.state[MARKER_KEY], true);
});

test("migration marker blocks a second import and workspace storage is never read", async () => {
  const storage = createStorageSpy({
    [STORAGE_KEY]: {
      version: 1,
      answers: [createSavedAnswerRecord("Website", "text", ["https://example.test"])]
    },
    [MARKER_KEY]: true,
    "nxjob.workspace.v1": { shouldNeverBeRead: true }
  });
  const service = createServiceStub({
    answers: [createSavedAnswerRecord("Website", "text", ["https://example.test"])]
  });
  __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });

  const first = await loadSavedAnswers();
  const second = await loadSavedAnswers();

  assert.equal(first.length, 1);
  assert.equal(second.length, 1);
  assert.equal(service.calls.imports.length, 0);
  assert.deepEqual(storage.calls.get, [MARKER_KEY]);
  assert.ok(!storage.calls.get.includes("nxjob.workspace.v1"));
});

test("service-backed CRUD uses local service as the only active source", async () => {
  const storage = createStorageSpy({
    [STORAGE_KEY]: { version: 1, answers: [] }
  });
  const service = createServiceStub();
  __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });

  const created = await saveConfirmedAnswer({
    question: "Portfolio website",
    fieldType: "text",
    answers: ["https://portfolio.example"],
    sensitive: false
  });
  await updateSavedAnswer(created.id, ["https://portfolio-new.example"]);
  await touchSavedAnswer(created.id);
  await deleteSavedAnswer(created.id);
  await clearSavedAnswers();

  assert.equal(service.calls.imports.length, 1);
  assert.equal(service.calls.creates.length, 1);
  assert.equal(service.calls.updates.length, 1);
  assert.equal(service.calls.touches.length, 1);
  assert.equal(service.calls.deletes.length, 1);
  assert.equal(service.calls.clears, 1);
  assert.equal(storage.state[STORAGE_KEY].answers.length, 0);
});

test("clipboard failure does not update answer recency", async () => {
  const storage = createStorageSpy({ [MARKER_KEY]: true });
  const saved = createSavedAnswerRecord("Portfolio website", "text", ["https://portfolio.example"]);
  const service = createServiceStub({ answers: [saved] });
  __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });

  await assert.rejects(
    copyAnswerAndTouch(saved.id, saved.answers[0], async () => {
      throw new Error("Clipboard permission denied");
    }),
    /Clipboard permission denied/
  );

  assert.equal(service.calls.touches.length, 0);
});

test("copy preflight failure does not write to the clipboard", async () => {
  const storage = createStorageSpy({ [MARKER_KEY]: true });
  const saved = createSavedAnswerRecord("Portfolio website", "text", ["https://portfolio.example"]);
  const service = createServiceStub({ answers: [saved], loadError: new Error("service stopped") });
  const clipboardWrites = [];
  __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });

  await assert.rejects(
    copyAnswerAndTouch(saved.id, saved.answers[0], async (value) => {
      clipboardWrites.push(value);
    }),
    (error) => {
      assert.equal(error.message, OFFLINE_MESSAGE);
      return true;
    }
  );

  assert.equal(service.calls.touches.length, 0);
  assert.deepEqual(clipboardWrites, []);
});

test("copy re-reads the canonical answer content before touching recency", async () => {
  const storage = createStorageSpy({ [MARKER_KEY]: true });
  const saved = createSavedAnswerRecord("Portfolio website", "text", ["https://portfolio.example"]);
  const service = createServiceStub({ answers: [saved] });
  const clipboardWrites = [];
  __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });

  await copyAnswerAndTouch(saved.id, "stale-ui-value", async (value) => {
    clipboardWrites.push(value);
  });

  assert.deepEqual(clipboardWrites, [saved.answers.join("\n")]);
  assert.deepEqual(service.calls.touches, [saved.id]);
});

test("copy fails before clipboard output when the requested record no longer exists", async () => {
  const storage = createStorageSpy({ [MARKER_KEY]: true });
  const service = createServiceStub({ answers: [] });
  const clipboardWrites = [];
  __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });

  await assert.rejects(
    copyAnswerAndTouch("missing-answer", "stale-ui-value", async (value) => {
      clipboardWrites.push(value);
    }),
    /There is no answer to copy\./
  );

  assert.deepEqual(clipboardWrites, []);
  assert.equal(service.calls.touches.length, 0);
});

test("candidate refresh behavior replaces stale values for copy save edit delete and clear", async () => {
  const field = createFieldFixture("LinkedIn profile URL", "field-linkedin");
  const initialRows = [
    {
      field,
      candidates: [
        {
          answer: createSavedAnswerRecord("LinkedIn profile URL", "text", ["stale-ui-value"]),
          score: 1,
          confidenceLabel: "High"
        }
      ]
    }
  ];

  const scenarios = [
    ["copy", [createSavedAnswerRecord("LinkedIn profile URL", "text", ["https://linkedin.example/current"])]],
    ["save", [createSavedAnswerRecord("LinkedIn profile URL", "text", ["https://linkedin.example/new"])]],
    ["edit", [createSavedAnswerRecord("LinkedIn profile URL", "text", ["https://linkedin.example/edited"])]],
    ["delete", []],
    ["clear", []]
  ];

  for (const [name, canonicalAnswers] of scenarios) {
    const refreshed = refreshAnswerCandidateRows(initialRows, canonicalAnswers);
    const values = refreshed[0].candidates.map((candidate) => candidate.answer.answers[0]);
    assert.ok(!values.includes("stale-ui-value"), `${name} should remove stale candidate values`);
    assert.deepEqual(values, canonicalAnswers.map((answer) => answer.answers[0]), name);
  }
});

test("mutation workflows reload canonical answers and apply refreshed candidate rows", async () => {
  const field = createFieldFixture("LinkedIn profile URL", "field-linkedin");
  const currentRecord = createSavedAnswerRecord("LinkedIn profile URL", "text", ["https://linkedin.example/current"]);
  currentRecord.id = "answer-current";
  const staleRecord = createSavedAnswerRecord("LinkedIn profile URL", "text", ["stale-ui-value"]);
  staleRecord.id = "answer-stale";
  const trackedRows = {
    "job-1": [
      {
        field,
        candidates: [
          {
            answer: staleRecord,
            score: 1,
            confidenceLabel: "High"
          }
        ]
      }
    ]
  };

  const scenarios = [
    {
      name: "copy",
      initialAnswers: [structuredClone(currentRecord)],
      mutate: async () => {
        await copyAnswerAndTouch("answer-current", "stale-ui-value", async () => {});
      },
      expectedValues: ["https://linkedin.example/current"]
    },
    {
      name: "save",
      initialAnswers: [],
      mutate: async () => {
        await saveConfirmedAnswer({
          question: "LinkedIn profile URL",
          fieldType: "text",
          answers: ["https://linkedin.example/new"],
          sensitive: false
        });
      },
      expectedValues: ["https://linkedin.example/new"]
    },
    {
      name: "edit",
      initialAnswers: [structuredClone(currentRecord)],
      mutate: async () => {
        await updateSavedAnswer("answer-current", ["https://linkedin.example/edited"]);
      },
      expectedValues: ["https://linkedin.example/edited"]
    },
    {
      name: "delete",
      initialAnswers: [structuredClone(currentRecord)],
      mutate: async () => {
        await deleteSavedAnswer("answer-current");
      },
      expectedValues: []
    },
    {
      name: "clear",
      initialAnswers: [structuredClone(currentRecord)],
      mutate: async () => {
        await clearSavedAnswers();
      },
      expectedValues: []
    }
  ];

  for (const scenario of scenarios) {
    const storage = createStorageSpy({ [MARKER_KEY]: true });
    const service = createServiceStub({ answers: scenario.initialAnswers });
    __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });

    let appliedAnswers = null;
    let trackedState = structuredClone(trackedRows);
    await runAnswerLibraryMutationAndRefreshCandidates(scenario.mutate, async (nextAnswers) => {
      appliedAnswers = nextAnswers;
      applyRefreshedTrackedAnswerCandidates(nextAnswers, (updater) => {
        trackedState = updater(trackedState);
      });
    });

    const values = trackedState["job-1"][0].candidates.map((candidate) => candidate.answer.answers[0]);
    assert.ok(!values.includes("stale-ui-value"), `${scenario.name} should remove stale candidate values`);
    assert.deepEqual(values, scenario.expectedValues, scenario.name);
    assert.deepEqual(
      appliedAnswers.map((answer) => answer.answers[0]),
      scenario.expectedValues,
      `${scenario.name} canonical answers`
    );
  }
});

test("functional candidate refresh preserves intervening rows while refreshing existing rows from canonical answers", async () => {
  const fieldOne = createFieldFixture("LinkedIn profile URL", "field-linkedin");
  const fieldTwo = createFieldFixture("Portfolio website", "field-portfolio");
  const trackedRows = {
    "job-1": [
      {
        field: fieldOne,
        candidates: [
          {
            answer: createSavedAnswerWithId("answer-stale", "LinkedIn profile URL", "text", ["stale-ui-value"]),
            score: 1,
            confidenceLabel: "High"
          }
        ]
      }
    ]
  };
  const canonicalAnswers = [
    createSavedAnswerWithId("answer-current", "LinkedIn profile URL", "text", ["https://linkedin.example/current"]),
    createSavedAnswerWithId("answer-portfolio", "Portfolio website", "text", ["https://portfolio.example"])
  ];
  let trackedState = structuredClone(trackedRows);

  applyRefreshedTrackedAnswerCandidates(canonicalAnswers, (updater) => {
    trackedState = {
      ...trackedState,
      "job-2": [
        {
          field: fieldTwo,
          candidates: [
            {
              answer: createSavedAnswerWithId("answer-portfolio", "Portfolio website", "text", ["https://portfolio.example"]),
              score: 1,
              confidenceLabel: "High"
            }
          ]
        }
      ]
    };
    trackedState = updater(trackedState);
  });

  assert.deepEqual(
    trackedState["job-1"][0].candidates.map((candidate) => candidate.answer.answers[0]),
    ["https://linkedin.example/current"]
  );
  assert.deepEqual(
    trackedState["job-2"][0].candidates.map((candidate) => candidate.answer.answers[0]),
    ["https://portfolio.example"]
  );
});

test("service-backed mutations return the fixed offline message when the service disappears", async () => {
  const storage = createStorageSpy({ [MARKER_KEY]: true });

  for (const [name, action, createStubOptions] of [
    [
      "create",
      () =>
        saveConfirmedAnswer({
          question: "Portfolio website",
          fieldType: "text",
          answers: ["https://portfolio.example"],
          sensitive: false
        }),
      { createError: new Error("backend stopped during create") }
    ],
    ["update", () => updateSavedAnswer("answer-1", ["updated"]), { updateError: new Error("backend stopped during update") }],
    ["delete", () => deleteSavedAnswer("answer-1"), { deleteError: new Error("backend stopped during delete") }],
    ["clear", () => clearSavedAnswers(), { clearError: new Error("backend stopped during clear") }],
    ["touch", () => touchSavedAnswer("answer-1"), { touchError: new Error("backend stopped during touch") }]
  ]) {
    const service = createServiceStub(createStubOptions);
    __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });
    await assert.rejects(
      action(),
      (error) => {
        assert.equal(error.message, OFFLINE_MESSAGE, name);
        return true;
      },
      name
    );
  }
});

test("service fetch failure becomes the fixed offline message and does not write the marker", async () => {
  const storage = createStorageSpy({
    [STORAGE_KEY]: {
      version: 1,
      answers: [createSavedAnswerRecord("Sensitive answer", "text", ["SECRET-123"], true)]
    }
  });
  const service = createServiceStub({ importError: new Error("SECRET-123 leaked from backend") });
  __setFormAnswerLibraryTestHooks({ storageArea: storage, serviceClient: service.client });

  await assert.rejects(loadSavedAnswers(), (error) => {
    assert.equal(error.message, OFFLINE_MESSAGE);
    return true;
  });
  assert.equal(storage.state[MARKER_KEY], undefined);
});

run();

function createSavedAnswerRecord(question, fieldType, answers, sensitive = false, lastUsedAt = "2026-07-05T00:00:00Z") {
  return {
    id: `answer-${Math.random().toString(36).slice(2, 10)}`,
    question,
    normalizedQuestion: normalizeQuestionForFixture(question),
    fieldType,
    answers,
    sensitive,
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-02T00:00:00Z",
    lastUsedAt
  };
}

function createSavedAnswerWithId(id, question, fieldType, answers, sensitive = false, lastUsedAt = "2026-07-05T00:00:00Z") {
  return {
    id,
    question,
    normalizedQuestion: normalizeQuestionForFixture(question),
    fieldType,
    answers,
    sensitive,
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-02T00:00:00Z",
    lastUsedAt
  };
}

function createStorageSpy(initialState = {}) {
  const state = structuredClone(initialState);
  const calls = { get: [], set: [], remove: [] };
  return {
    state,
    calls,
    async get(key) {
      calls.get.push(key);
      assert.equal(typeof key, "string");
      return { [key]: state[key] };
    },
    async set(value) {
      calls.set.push(structuredClone(value));
      Object.assign(state, structuredClone(value));
    },
    async remove(key) {
      calls.remove.push(key);
      delete state[key];
    }
  };
}

function createServiceStub(options = {}) {
  const answers = structuredClone(options.answers ?? []);
  const calls = {
    imports: [],
    creates: [],
    updates: [],
    touches: [],
    deletes: [],
    clears: 0
  };
  return {
    calls,
    client: {
      async load() {
        if (options.loadError) throw options.loadError;
        return structuredClone(answers);
      },
      async importAnswers(payload) {
        calls.imports.push(structuredClone(payload));
        if (options.importError) throw options.importError;
        answers.splice(0, answers.length, ...structuredClone(payload.answers));
      },
      async create(input) {
        calls.creates.push(structuredClone(input));
        if (options.createError) throw options.createError;
        const created = createSavedAnswerRecord(input.question, input.fieldType, input.answers, input.sensitive);
        answers.unshift(created);
        return structuredClone(created);
      },
      async update(id, nextAnswers) {
        calls.updates.push({ id, answers: structuredClone(nextAnswers) });
        if (options.updateError) throw options.updateError;
        const record = answers.find((entry) => entry.id === id);
        if (record) {
          record.answers = structuredClone(nextAnswers);
          record.updatedAt = "2026-07-06T00:00:00Z";
          record.lastUsedAt = "2026-07-06T00:00:00Z";
        }
      },
      async touch(id) {
        calls.touches.push(id);
        if (options.touchError) throw options.touchError;
        const record = answers.find((entry) => entry.id === id);
        if (record) {
          record.lastUsedAt = "2026-07-07T00:00:00Z";
        }
      },
      async delete(id) {
        calls.deletes.push(id);
        if (options.deleteError) throw options.deleteError;
        const index = answers.findIndex((entry) => entry.id === id);
        if (index >= 0) answers.splice(index, 1);
      },
      async clear() {
        calls.clears += 1;
        if (options.clearError) throw options.clearError;
        answers.splice(0, answers.length);
      }
    }
  };
}

function normalizeQuestionForFixture(question) {
  return question
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function createFieldFixture(questionText, fieldId) {
  return {
    questionText,
    inputType: "text",
    required: false,
    sensitiveKind: "",
    recognitionConfidence: 0.98,
    fieldId
  };
}
