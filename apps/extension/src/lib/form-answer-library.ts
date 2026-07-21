import { browser } from "wxt/browser";

import type { DetectedFormField } from "./form-context";

const STORAGE_KEY = "nxjob.form-answer-library.v1";
const STORAGE_VERSION = 1;
const MAX_MATCHES = 3;

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

const memoryStorage = new Map<string, unknown>();

function storageArea(): StorageAreaLike {
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

export async function loadSavedAnswers(): Promise<SavedAnswer[]> {
  const payload = await loadPayload();
  return payload.answers;
}

export async function saveConfirmedAnswer(input: SaveConfirmedAnswerInput): Promise<SavedAnswer> {
  const payload = await loadPayload();
  const now = new Date().toISOString();
  const answers = normalizeAnswers(input.answers);
  const normalizedQuestion = normalizeQuestion(input.question);
  const existing = payload.answers.find(
    (entry) =>
      entry.normalizedQuestion === normalizedQuestion &&
      entry.fieldType === input.fieldType &&
      sameAnswers(entry.answers, answers)
  );

  if (existing) {
    const updated: SavedAnswer = {
      ...existing,
      question: input.question.trim() || existing.question,
      sensitive: input.sensitive,
      updatedAt: now,
      lastUsedAt: now
    };
    await savePayload({
      version: STORAGE_VERSION,
      answers: payload.answers.map((entry) => (entry.id === existing.id ? updated : entry))
    });
    return updated;
  }

  const saved: SavedAnswer = {
    id: `answer-${Math.random().toString(36).slice(2, 10)}`,
    question: input.question.trim(),
    normalizedQuestion,
    fieldType: input.fieldType,
    answers,
    sensitive: input.sensitive,
    createdAt: now,
    updatedAt: now,
    lastUsedAt: now
  };
  await savePayload({
    version: STORAGE_VERSION,
    answers: [saved, ...payload.answers]
  });
  return saved;
}

export async function updateSavedAnswer(id: string, answers: string[]): Promise<void> {
  const payload = await loadPayload();
  const nextAnswers = normalizeAnswers(answers);
  const now = new Date().toISOString();
  await savePayload({
    version: STORAGE_VERSION,
    answers: payload.answers.map((entry) =>
      entry.id === id
        ? {
            ...entry,
            answers: nextAnswers,
            updatedAt: now,
            lastUsedAt: now
          }
        : entry
    )
  });
}

export async function deleteSavedAnswer(id: string): Promise<void> {
  const payload = await loadPayload();
  await savePayload({
    version: STORAGE_VERSION,
    answers: payload.answers.filter((entry) => entry.id !== id)
  });
}

export async function clearSavedAnswers(): Promise<void> {
  await storageArea().remove(STORAGE_KEY);
}

export async function touchSavedAnswer(id: string): Promise<void> {
  const payload = await loadPayload();
  const now = new Date().toISOString();
  await savePayload({
    version: STORAGE_VERSION,
    answers: payload.answers.map((entry) =>
      entry.id === id
        ? {
            ...entry,
            lastUsedAt: now
          }
        : entry
    )
  });
}

export async function copyAnswerAndTouch(
  id: string,
  value: string,
  writeToClipboard: (value: string) => Promise<void>
): Promise<void> {
  await writeToClipboard(value);
  await touchSavedAnswer(id);
}

export async function findAnswerCandidates(field: DetectedFormField): Promise<AnswerCandidate[]> {
  if (!field.questionText.trim()) return [];

  const profile = buildQuestionProfile(field.questionText);
  const answers = await loadSavedAnswers();

  const matches = answers
    .filter((entry) => entry.fieldType === field.inputType)
    .map((entry) => ({ entry, profile: buildQuestionProfile(entry.question) }))
    .filter(({ profile: candidateProfile }) => areProfilesCompatible(profile, candidateProfile))
    .map(({ entry, profile: candidateProfile }) => {
      const score =
        entry.normalizedQuestion === profile.normalized
          ? 1
          : lexicalScore(profile.tokens, candidateProfile.tokens);
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

export async function __resetFormAnswerLibraryForTest(): Promise<void> {
  memoryStorage.clear();
  await clearSavedAnswers();
}

async function loadPayload(): Promise<StoragePayload> {
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

async function savePayload(payload: StoragePayload): Promise<void> {
  await storageArea().set({
    [STORAGE_KEY]: payload
  });
}

function normalizeSavedAnswer(value: unknown): SavedAnswer | null {
  if (!value || typeof value !== "object") return null;
  const entry = value as Partial<SavedAnswer>;
  if (typeof entry.id !== "string" || typeof entry.question !== "string" || typeof entry.normalizedQuestion !== "string") {
    return null;
  }
  const answers = Array.isArray(entry.answers) ? normalizeAnswers(entry.answers) : [];
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

function sameAnswers(left: string[], right: string[]): boolean {
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}

export function normalizeQuestion(question: string): string {
  return question
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
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
