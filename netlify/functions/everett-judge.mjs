import { createHash, randomUUID, webcrypto } from "node:crypto";

import { getDatabase } from "@netlify/database";

const APP_ID = "35575132-c9c1-493c-9283-fd5eb6f48f0a";
const RUN_URL = "https://unique-marzipan-a7a3f0.netlify.app/.netlify/functions/everett-judge";
const DEFAULT_JWKS_URL = "https://api.ginse.ai/.well-known/jwks.json";
const SCORE_DIFF_PENALTY = 0.005;
const cryptoApi = globalThis.crypto ?? webcrypto;

let jwksCache = { expiresAt: 0, keys: [] };

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

function fail(code, message, status) {
  return json({ error: { code, message } }, status);
}

function hasOnlyKeys(value, keys) {
  return Object.keys(value).every((key) => keys.includes(key));
}

function isPositiveNumber(value) {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function validateInput(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) || !hasOnlyKeys(value, ["baseline_p50_ms", "candidates"])) {
    throw new Error("Input must contain only baseline_p50_ms and candidates.");
  }
  if (!isPositiveNumber(value.baseline_p50_ms)) {
    throw new Error("baseline_p50_ms must be a positive number.");
  }
  if (!Array.isArray(value.candidates) || value.candidates.length < 1 || value.candidates.length > 3) {
    throw new Error("candidates must contain between one and three benchmarked changes.");
  }

  const seenIds = new Set();
  const candidates = value.candidates.map((candidate) => {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate) || !hasOnlyKeys(candidate, ["id", "strategy", "p50_ms", "diff_lines", "tests_passed"])) {
      throw new Error("Each candidate must contain only id, strategy, p50_ms, diff_lines, and tests_passed.");
    }
    if (typeof candidate.id !== "string" || !/^[A-Za-z0-9_-]{1,24}$/.test(candidate.id) || seenIds.has(candidate.id)) {
      throw new Error("Each candidate id must be unique and contain only letters, numbers, underscores, or hyphens.");
    }
    seenIds.add(candidate.id);
    if (typeof candidate.strategy !== "string" || candidate.strategy.trim().length < 3 || candidate.strategy.length > 280) {
      throw new Error("Each candidate strategy must be between 3 and 280 characters.");
    }
    if (!isPositiveNumber(candidate.p50_ms)) {
      throw new Error("Each candidate p50_ms must be a positive number.");
    }
    if (!Number.isInteger(candidate.diff_lines) || candidate.diff_lines < 0) {
      throw new Error("Each candidate diff_lines must be a non-negative integer.");
    }
    if (typeof candidate.tests_passed !== "boolean") {
      throw new Error("Each candidate tests_passed value must be boolean.");
    }
    return { ...candidate, strategy: candidate.strategy.trim() };
  });

  return { baseline_p50_ms: value.baseline_p50_ms, candidates };
}

function rankCandidates({ baseline_p50_ms, candidates }) {
  const scoreboard = candidates.map((candidate) => {
    const speedup = baseline_p50_ms / candidate.p50_ms;
    const score = candidate.tests_passed ? speedup - SCORE_DIFF_PENALTY * candidate.diff_lines : 0;
    return { ...candidate, speedup, score };
  });
  const passing = scoreboard.filter((candidate) => candidate.tests_passed).sort((left, right) => right.score - left.score);
  if (!passing.length) {
    throw new Error("At least one candidate must pass its correctness tests before Everett can select a winner.");
  }

  const winner = passing[0];
  const runnerUp = passing[1];
  const scoreMargin = runnerUp ? winner.score - runnerUp.score : winner.score;
  return {
    baseline_p50_ms,
    winner,
    scoreboard,
    decision_evidence: {
      hard_gate: "tests_passing",
      speedup: winner.speedup,
      diff_lines: winner.diff_lines,
      score_margin: scoreMargin,
      summary: `Timeline ${winner.id} passed correctness tests and earned the highest score after the ${SCORE_DIFF_PENALTY} per-line change penalty.`,
    },
  };
}

function validateOutput(output) {
  const { winner, scoreboard, decision_evidence } = output;
  if (!isPositiveNumber(output.baseline_p50_ms) || !winner?.tests_passed || !Array.isArray(scoreboard) || !scoreboard.length) {
    throw new Error("Generated result does not match the advertised output contract.");
  }
  if (!isPositiveNumber(winner.p50_ms) || !isPositiveNumber(winner.speedup) || !Number.isInteger(winner.diff_lines) || typeof winner.score !== "number" || winner.score < 0) {
    throw new Error("Winner result is invalid.");
  }
  if (!decision_evidence || decision_evidence.hard_gate !== "tests_passing" || !isPositiveNumber(decision_evidence.speedup) || !Number.isInteger(decision_evidence.diff_lines) || typeof decision_evidence.score_margin !== "number" || typeof decision_evidence.summary !== "string") {
    throw new Error("Decision evidence is invalid.");
  }
  for (const entry of scoreboard) {
    if (!entry || typeof entry.id !== "string" || typeof entry.strategy !== "string" || typeof entry.tests_passed !== "boolean" || !isPositiveNumber(entry.p50_ms) || !isPositiveNumber(entry.speedup) || !Number.isInteger(entry.diff_lines) || typeof entry.score !== "number" || entry.score < 0) {
      throw new Error("Scoreboard result is invalid.");
    }
  }
}

function canonicalize(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function fingerprint(value) {
  return createHash("sha256").update(canonicalize(value)).digest("hex");
}

function decodeBase64Url(value) {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) throw new Error("Malformed token.");
  return new Uint8Array(Buffer.from(value, "base64url"));
}

function decodeJson(value) {
  return JSON.parse(Buffer.from(decodeBase64Url(value)).toString("utf8"));
}

function jwksUrlFromHeader(header) {
  if (!header.jku) return DEFAULT_JWKS_URL;
  const url = new URL(header.jku);
  if (url.protocol !== "https:" || url.hostname !== "api.ginse.ai") {
    throw new Error("Token key source is not trusted.");
  }
  return url.href;
}

async function publicKeys(url) {
  if (jwksCache.expiresAt > Date.now()) return jwksCache.keys;
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Ginse signing keys are unavailable.");
  const document = await response.json();
  if (!document || !Array.isArray(document.keys)) throw new Error("Ginse signing keys are malformed.");
  jwksCache = { expiresAt: Date.now() + 300_000, keys: document.keys };
  return document.keys;
}

async function verifyGinseBearer(request) {
  const authorization = request.headers.get("authorization") || "";
  const match = authorization.match(/^Bearer ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$/);
  if (!match) throw new Error("A Ginse bearer token is required.");

  const [headerPart, payloadPart, signaturePart] = match[1].split(".");
  const header = decodeJson(headerPart);
  if (header.alg !== "EdDSA" || typeof header.kid !== "string" || !header.kid) {
    throw new Error("Bearer token must use a Ginse Ed25519 signing key.");
  }
  const keys = await publicKeys(jwksUrlFromHeader(header));
  const jwk = keys.find((candidate) => candidate.kid === header.kid && candidate.kty === "OKP" && candidate.crv === "Ed25519");
  if (!jwk) throw new Error("Bearer token signing key is unknown.");
  const key = await cryptoApi.subtle.importKey("jwk", jwk, { name: "Ed25519", namedCurve: "Ed25519" }, false, ["verify"]);
  const valid = await cryptoApi.subtle.verify({ name: "Ed25519" }, key, decodeBase64Url(signaturePart), new TextEncoder().encode(`${headerPart}.${payloadPart}`));
  if (!valid) throw new Error("Bearer token signature is invalid.");

  const claims = decodeJson(payloadPart);
  const now = Math.floor(Date.now() / 1000);
  if (!Number.isFinite(claims.exp) || claims.exp <= now || (Number.isFinite(claims.nbf) && claims.nbf > now)) {
    throw new Error("Bearer token is expired or not active.");
  }
  if (claims.app_id && claims.app_id !== APP_ID) throw new Error("Bearer token belongs to a different Ginse app.");
  if (claims.run_url && claims.run_url !== RUN_URL) throw new Error("Bearer token belongs to a different Ginse endpoint.");
  if (claims.aud) {
    const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    const accepted = new Set([APP_ID, "everett-optimization-judge", RUN_URL, new URL(RUN_URL).origin]);
    if (!audiences.some((audience) => accepted.has(audience))) throw new Error("Bearer token audience is invalid.");
  }
}

function normalizeStoredOutput(value) {
  return typeof value === "string" ? JSON.parse(value) : value;
}

export default async (request) => {
  if (request.method !== "POST") return fail("method_not_allowed", "Use POST for Everett optimization judgments.", 405);

  try {
    await verifyGinseBearer(request);
  } catch (error) {
    return fail("unauthorized", error instanceof Error ? error.message : "Invalid Ginse bearer token.", 401);
  }

  const idempotencyKey = request.headers.get("idempotency-key") || "";
  if (!/^[A-Za-z0-9._:-]{1,200}$/.test(idempotencyKey)) {
    return fail("invalid_idempotency_key", "Idempotency-Key must be 1-200 safe characters.", 400);
  }

  let input;
  try {
    input = validateInput(await request.json());
  } catch (error) {
    return fail("invalid_input", error instanceof Error ? error.message : "Input must be valid JSON.", 400);
  }

  let output;
  try {
    output = rankCandidates(input);
    validateOutput(output);
  } catch (error) {
    return fail("no_safe_winner", error instanceof Error ? error.message : "Everett could not select a safe winner.", 422);
  }

  const requestFingerprint = fingerprint(input);
  const providerOperationId = randomUUID();
  const database = getDatabase();
  try {
    const inserted = await database.sql`
      INSERT INTO ginse_operations (idempotency_key, request_fingerprint, provider_operation_id, status, output)
      VALUES (${idempotencyKey}, ${requestFingerprint}, ${providerOperationId}, 'succeeded', ${JSON.stringify(output)}::jsonb)
      ON CONFLICT (idempotency_key) DO NOTHING
      RETURNING provider_operation_id, output
    `;
    if (inserted.length) {
      return json({ status: "succeeded", provider_operation_id: inserted[0].provider_operation_id, replayed: false, output });
    }

    const existing = await database.sql`
      SELECT request_fingerprint, provider_operation_id, output
      FROM ginse_operations
      WHERE idempotency_key = ${idempotencyKey}
      LIMIT 1
    `;
    if (!existing.length) throw new Error("Idempotency record could not be read after an insert conflict.");
    if (existing[0].request_fingerprint !== requestFingerprint) {
      return fail("idempotency_conflict", "This Idempotency-Key was already used with a different request.", 409);
    }
    return json({
      status: "succeeded",
      provider_operation_id: existing[0].provider_operation_id,
      replayed: true,
      output: normalizeStoredOutput(existing[0].output),
    });
  } catch (error) {
    return fail("provider_storage_error", "Everett could not persist this optimization judgment.", 503);
  }
};
