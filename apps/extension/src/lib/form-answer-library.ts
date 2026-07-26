import { browser } from "wxt/browser";

import type { SavedAnswerRecord as ServiceSavedAnswer } from "./api-client";
import {
  clearFormAnswerLibrary,
  createFormAnswerLibraryAnswer,
  deleteFormAnswerLibraryAnswer,
  getFormAnswerLibrary,
  importFormAnswerLibrary,
  touchFormAnswerLibraryAnswer,
  updateFormAnswerLibraryAnswer
} from "./api-client";
import type { DetectedFormField } from "./form-context";

const STORAGE_KEY = "nxjob.form-answer-library.v1";
const MIGRATION_MARKER_KEY = "nxjob.form-answer-library.service-imported.v1";
const STORAGE_VERSION = 1;
const MAX_MATCHES = 3;
const SERVICE_UNAVAILABLE_MESSAGE = "Local Service is unavailable. Start it to use saved answers.";

type StoragePayload = {
  version: number;
  answers: SavedAnswer[];
};

export type SavedAnswerFieldType = DetectedFormField["inputType"];

export type SavedAnswer = {
  id: string;
  question: string;
  normalizedQuestion: string;
  fieldType: SavedAnswerFieldType;
  answers: string[];
  sensitive: boolean;
  createdAt: string;
  updatedAt: string;
  lastUsedAt: string;
};

export type AnswerCandidate = {
  answer: SavedAnswer;
  score: number;
  confidenceLabel: "High" | "Possible";
};

type SaveConfirmedAnswerInput = {
  question: string;
  fieldType: SavedAnswerFieldType;
  answers: string[];
  sensitive: boolean;
};

type QuestionProfile = {
  normalized: string;
  family:
    | "work_authorization"
    | "visa_sponsorship"
    | "salary"
    | "relocation"
    | "availability"
    | "links_contact"
    | "eeo_disclosure"
    | "generic";
  tokens: string[];
  countryExpression: string;
  nameRoles: string[];
  eeoFacets: string[];
  timeQualifier: string;
  negation: "positive" | "negative" | "";
  keyQualifier: string;
};

type StorageAreaLike = {
  get(key: string): Promise<Record<string, unknown>>;
  set(value: Record<string, unknown>): Promise<void>;
  remove(key: string): Promise<void>;
};

type FormAnswerServiceClient = {
  load(): Promise<SavedAnswer[]>;
  importAnswers(payload: { version: 1; answers: SavedAnswer[] }): Promise<void>;
  create(input: SaveConfirmedAnswerInput): Promise<SavedAnswer>;
  update(id: string, answers: string[]): Promise<void>;
  touch(id: string): Promise<void>;
  delete(id: string): Promise<void>;
  clear(): Promise<void>;
};

type TestHooks = {
  storageArea?: StorageAreaLike;
  serviceClient?: FormAnswerServiceClient;
};

const memoryStorage = new Map<string, unknown>();
let testHooks: TestHooks = {};
let migrationPromise: Promise<void> | null = null;

function defaultStorageArea(): StorageAreaLike {
  if (browser?.storage?.local) {
    return browser.storage.local as StorageAreaLike;
  }
  return {
    async get(key) {
      return { [key]: memoryStorage.get(key) };
    },
    async set(value) {
      for (const [key, entry] of Object.entries(value)) {
        memoryStorage.set(key, entry);
      }
    },
    async remove(key) {
      memoryStorage.delete(key);
    }
  };
}

function storageArea(): StorageAreaLike {
  return testHooks.storageArea ?? defaultStorageArea();
}

function defaultServiceClient(): FormAnswerServiceClient {
  return {
    async load() {
      const response = await getFormAnswerLibrary();
      return response.answers.map(normalizeSavedAnswer).filter(Boolean) as SavedAnswer[];
    },
    async importAnswers(payload) {
      await importFormAnswerLibrary({ version: 1, answers: payload.answers });
    },
    async create(input) {
      const response = await createFormAnswerLibraryAnswer(input);
      const normalized = normalizeSavedAnswer(response.answer);
      if (!normalized) throw new Error("Local Service returned an invalid saved answer.");
      return normalized;
    },
    async update(id, answers) {
      await updateFormAnswerLibraryAnswer(id, { answers });
    },
    async touch(id) {
      await touchFormAnswerLibraryAnswer(id);
    },
    async delete(id) {
      await deleteFormAnswerLibraryAnswer(id);
    },
    async clear() {
      await clearFormAnswerLibrary();
    }
  };
}

function serviceClient(): FormAnswerServiceClient {
  return testHooks.serviceClient ?? defaultServiceClient();
}

export async function loadSavedAnswers(): Promise<SavedAnswer[]> {
  await ensureServiceImport();
  return fetchSavedAnswersFromService();
}

export async function saveConfirmedAnswer(input: SaveConfirmedAnswerInput): Promise<SavedAnswer> {
  await ensureServiceImport();
  return withServiceUnavailableMessage(() => serviceClient().create(input));
}

export async function updateSavedAnswer(id: string, answers: string[]): Promise<void> {
  await ensureServiceImport();
  const normalized = normalizeAnswers(answers);
  await withServiceUnavailableMessage(() => serviceClient().update(id, normalized));
}

export async function deleteSavedAnswer(id: string): Promise<void> {
  await ensureServiceImport();
  await withServiceUnavailableMessage(() => serviceClient().delete(id));
}

export async function clearSavedAnswers(): Promise<void> {
  await ensureServiceImport();
  await withServiceUnavailableMessage(() => serviceClient().clear());
}

export async function preflightSavedAnswersService(): Promise<void> {
  await ensureServiceImport();
  await withServiceUnavailableMessage(async () => {
    await serviceClient().load();
  });
}

export async function touchSavedAnswer(id: string): Promise<void> {
  await ensureServiceImport();
  await withServiceUnavailableMessage(() => serviceClient().touch(id));
}

export async function copyAnswerAndTouch(
  id: string,
  _value: string,
  writeToClipboard: (value: string) => Promise<void>
): Promise<void> {
  await ensureServiceImport();
  const currentValue = await loadSavedAnswerContent(id);
  await writeToClipboard(currentValue);
  await touchSavedAnswer(id);
}

export function isSavedAnswersUnavailableError(error: unknown): boolean {
  return error instanceof Error && error.message === SERVICE_UNAVAILABLE_MESSAGE;
}

export function findAnswerCandidates(field: DetectedFormField, answers: SavedAnswer[]): AnswerCandidate[] {
  if (!field.questionText.trim()) return [];

  const profile = buildQuestionProfile(field.questionText);
  const matches = answers
    .filter((entry) => entry.fieldType === field.inputType)
    .map((entry) => ({ entry, profile: buildQuestionProfile(entry.question) }))
    .filter(({ profile: candidateProfile }) => areProfilesCompatible(profile, candidateProfile))
    .map(({ entry, profile: candidateProfile }) => {
      const score =
        entry.normalizedQuestion === profile.normalized ? 1 : lexicalScore(profile.tokens, candidateProfile.tokens);
      return { answer: entry, score };
    })
    .filter((item) => item.score >= 0.6)
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      return Date.parse(right.answer.lastUsedAt) - Date.parse(left.answer.lastUsedAt);
    })
    .slice(0, MAX_MATCHES)
    .map((item) => ({
      ...item,
      confidenceLabel: (item.score >= 0.9 ? "High" : "Possible") as "High" | "Possible"
    }));

  return matches;
}

export function refreshAnswerCandidateRows<TRow extends { field: DetectedFormField }>(
  rows: TRow[],
  answers: SavedAnswer[]
): Array<TRow & { candidates: AnswerCandidate[] }> {
  return rows.map((row) => ({
    ...row,
    candidates: findAnswerCandidates(row.field, answers)
  }));
}

export function refreshTrackedAnswerCandidateRows<TRow extends { field: DetectedFormField }>(
  trackedRows: Record<string, TRow[]>,
  answers: SavedAnswer[]
): Record<string, Array<TRow & { candidates: AnswerCandidate[] }>> {
  return Object.fromEntries(
    Object.entries(trackedRows).map(([key, rows]) => [key, refreshAnswerCandidateRows(rows, answers)])
  );
}

export function applyRefreshedTrackedAnswerCandidates<TRow extends { field: DetectedFormField }>(
  answers: SavedAnswer[],
  applyTrackedRowsUpdate: (
    updater: (current: Record<string, TRow[]>) => Record<string, Array<TRow & { candidates: AnswerCandidate[] }>>
  ) => void
): void {
  applyTrackedRowsUpdate((current) => refreshTrackedAnswerCandidateRows(current, answers));
}

export async function runAnswerLibraryMutationAndRefreshCandidates(
  mutate: () => Promise<void>,
  applyRefreshedRows: (answers: SavedAnswer[]) => Promise<void> | void
): Promise<SavedAnswer[]> {
  await mutate();
  const answers = await loadSavedAnswers();
  await applyRefreshedRows(answers);
  return answers;
}

export async function __resetFormAnswerLibraryForTest(): Promise<void> {
  memoryStorage.clear();
  testHooks = {};
  migrationPromise = null;
}

export function __setFormAnswerLibraryTestHooks(hooks: TestHooks): void {
  testHooks = hooks;
  migrationPromise = null;
}

async function ensureServiceImport(): Promise<void> {
  if (migrationPromise) {
    return migrationPromise;
  }

  migrationPromise = (async () => {
    const marker = await readMigrationMarker();
    if (marker) return;

    const payload = await loadLegacyPayload();
    await withServiceUnavailableMessage(() =>
      serviceClient().importAnswers({
        version: 1,
        answers: payload.answers
      })
    );
    await writeMigrationMarker();
  })();

  try {
    await migrationPromise;
  } catch (error) {
    migrationPromise = null;
    throw error;
  }
}

async function fetchSavedAnswersFromService(): Promise<SavedAnswer[]> {
  return withServiceUnavailableMessage(() => serviceClient().load());
}

async function loadSavedAnswerContent(id: string): Promise<string> {
  const answer = (await fetchSavedAnswersFromService()).find((entry) => entry.id === id);
  const value = answer?.answers.join("\n").trim() ?? "";
  if (!value) {
    throw new Error("There is no answer to copy.");
  }
  return value;
}

async function readMigrationMarker(): Promise<boolean> {
  const stored = await storageArea().get(MIGRATION_MARKER_KEY);
  return stored[MIGRATION_MARKER_KEY] === true;
}

async function writeMigrationMarker(): Promise<void> {
  await storageArea().set({ [MIGRATION_MARKER_KEY]: true });
}

async function loadLegacyPayload(): Promise<StoragePayload> {
  const stored = await storageArea().get(STORAGE_KEY);
  const raw = stored[STORAGE_KEY];
  if (!raw || typeof raw !== "object") {
    return { version: STORAGE_VERSION, answers: [] };
  }

  const payload = raw as Partial<StoragePayload>;
  if (payload.version !== STORAGE_VERSION || !Array.isArray(payload.answers)) {
    return { version: STORAGE_VERSION, answers: [] };
  }

  return {
    version: STORAGE_VERSION,
    answers: payload.answers.map(normalizeSavedAnswer).filter(Boolean) as SavedAnswer[]
  };
}

function normalizeSavedAnswer(value: unknown): SavedAnswer | null {
  if (!value || typeof value !== "object") return null;
  const entry = value as Partial<SavedAnswer> | Partial<ServiceSavedAnswer>;
  if (typeof entry.id !== "string" || typeof entry.question !== "string" || typeof entry.normalizedQuestion !== "string") {
    return null;
  }
  const answers = Array.isArray(entry.answers) ? normalizeAnswers(entry.answers as string[]) : [];
  if (answers.length === 0) return null;
  return {
    id: entry.id,
    question: entry.question,
    normalizedQuestion: entry.normalizedQuestion,
    fieldType: normalizeFieldType(entry.fieldType),
    answers,
    sensitive: Boolean(entry.sensitive),
    createdAt: typeof entry.createdAt === "string" ? entry.createdAt : "",
    updatedAt: typeof entry.updatedAt === "string" ? entry.updatedAt : "",
    lastUsedAt: typeof entry.lastUsedAt === "string" ? entry.lastUsedAt : ""
  };
}

function normalizeFieldType(value: unknown): SavedAnswerFieldType {
  switch (value) {
    case "text":
    case "textarea":
    case "radio":
    case "checkbox":
    case "select":
    case "custom_select":
      return value;
    default:
      return "text";
  }
}

function normalizeAnswers(values: string[]): string[] {
  return values.map((value) => value.trim()).filter(Boolean);
}

export function normalizeQuestion(question: string): string {
  return question
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function withServiceUnavailableMessage<T>(action: () => Promise<T>): Promise<T> {
  try {
    return await action();
  } catch {
    throw new Error(SERVICE_UNAVAILABLE_MESSAGE);
  }
}

function buildQuestionProfile(question: string): QuestionProfile {
  const normalized = normalizeQuestion(question);
  const tokens = normalized
    .split(" ")
    .filter(Boolean)
    .filter((token) => !STOP_WORDS.has(token));

  return {
    normalized,
    family: detectFamily(normalized),
    tokens,
    countryExpression: detectCountryExpression(question),
    nameRoles: detectNameRoles(normalized),
    eeoFacets: detectEeoFacets(normalized),
    timeQualifier: detectTimeQualifier(normalized),
    negation: detectNegation(normalized),
    keyQualifier: detectKeyQualifier(normalized)
  };
}

function detectFamily(question: string): QuestionProfile["family"] {
  if (/(authorized to work|work authorization|legally authorized)/.test(question)) return "work_authorization";
  if (/(visa sponsorship|sponsorship|require sponsor)/.test(question)) return "visa_sponsorship";
  if (/(salary|compensation|pay rate|hourly rate|annual pay|expected pay|current pay)/.test(question)) return "salary";
  if (/(relocat|move for this role|willing to move)/.test(question)) return "relocation";
  if (/(when can you start|when could you start|available to start|start date|notice period|how soon)/.test(question)) {
    return "availability";
  }
  if (/(linkedin|portfolio|github|website|url|phone|email|contact)/.test(question)) return "links_contact";
  if (/(veteran|disability|gender|race|ethnicity|sexual orientation|self identify|eeo)/.test(question)) {
    return "eeo_disclosure";
  }
  return "generic";
}

function detectCountryExpression(question: string): string {
  const match = question.match(/\b(?:in|within)\s+(?:the\s+)?(.+?)(?:[?.!,;:]|$)/i);
  return match ? normalizeQuestion(match[1]) : "";
}

function detectNameRoles(question: string): string[] {
  const roles = ["first", "last", "middle", "legal", "preferred", "given", "family"];
  return roles.filter((role) => new RegExp(`\\b${role}\\b`).test(question));
}

function detectEeoFacets(question: string): string[] {
  const facets = ["disability", "veteran", "race", "ethnicity", "gender", "sexual_orientation"];
  return facets.filter((facet) => {
    const pattern = facet === "sexual_orientation" ? /\bsexual orientation\b/ : new RegExp(`\\b${facet}\\b`);
    return pattern.test(question);
  });
}

function detectTimeQualifier(question: string): string {
  if (/\bnow or in the future\b/.test(question)) return "now_or_future";
  if (/\bcurrently\b/.test(question)) return "current";
  if (/\bhow soon\b/.test(question)) return "relative";
  if (/\bstart date\b/.test(question)) return "date";
  if (/\bnotice period\b/.test(question)) return "notice";
  return "";
}

function detectNegation(question: string): "positive" | "negative" | "" {
  if (/\b(no|not|without|never)\b/.test(question)) return "negative";
  if (/\b(yes|authorized|require|willing|available)\b/.test(question)) return "positive";
  return "";
}

function detectKeyQualifier(question: string): string {
  if (/\bcurrent salary\b/.test(question)) return "current_salary";
  if (/\bexpected salary\b/.test(question)) return "expected_salary";
  if (/\blinkedin\b/.test(question)) return "linkedin";
  if (/\bgithub\b/.test(question)) return "github";
  if (/\bportfolio\b/.test(question)) return "portfolio";
  if (/\bemail\b/.test(question)) return "email";
  if (/\bphone\b/.test(question)) return "phone";
  return "";
}

function areProfilesCompatible(left: QuestionProfile, right: QuestionProfile): boolean {
  if (left.normalized === right.normalized) return true;
  if (left.family === "generic" || right.family === "generic") return false;
  if (left.family !== right.family) return false;
  if (!sameSingleQualifier(left.countryExpression, right.countryExpression)) return false;
  if (left.family === "work_authorization" && !left.countryExpression) return false;
  if (!sameQualifier(left.nameRoles, right.nameRoles)) return false;
  if (!sameQualifier(left.eeoFacets, right.eeoFacets)) return false;
  if (!sameSingleQualifier(left.timeQualifier, right.timeQualifier)) return false;
  if (!sameSingleQualifier(left.keyQualifier, right.keyQualifier)) return false;
  if (!sameSingleQualifier(left.negation, right.negation)) return false;
  return true;
}

function sameQualifier(left: string[], right: string[]): boolean {
  if (left.length === 0 && right.length === 0) return true;
  if (left.length === 0 || right.length === 0) return false;
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}

function sameSingleQualifier(left: string, right: string): boolean {
  if (!left && !right) return true;
  if (!left || !right) return false;
  return left === right;
}

function lexicalScore(left: string[], right: string[]): number {
  const leftSet = new Set(left);
  const rightSet = new Set(right);
  const intersection = left.filter((token) => rightSet.has(token)).length;
  if (intersection === 0) return 0;
  return (2 * intersection) / (leftSet.size + rightSet.size);
}

const STOP_WORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "be",
  "can",
  "do",
  "for",
  "in",
  "is",
  "of",
  "or",
  "please",
  "the",
  "to",
  "will",
  "with",
  "you",
  "your"
]);
