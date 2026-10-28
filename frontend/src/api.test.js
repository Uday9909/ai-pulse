import test from "node:test";
import assert from "node:assert/strict";

import { api } from "./api.js";

globalThis.localStorage = { getItem: () => null };

test("a non-JSON error body still yields a status-bearing error", async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 500,
    json: async () => {
      throw new SyntaxError("Unexpected token");
    },
  });

  await assert.rejects(
    () => api("/boom"),
    (error) => {
      assert.equal(error.status, 500);
      assert.match(error.message, /500/);
      return true;
    },
  );
});

test("a JSON error keeps the server detail and status", async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 409,
    json: async () => ({ detail: "Question already answered: common-freq" }),
  });

  await assert.rejects(
    () => api("/diagnostic/submit", { method: "POST" }),
    (error) => {
      assert.equal(error.status, 409);
      assert.equal(error.message, "Question already answered: common-freq");
      return true;
    },
  );
});

test("a successful response returns parsed json", async () => {
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ ok: true }) });

  assert.deepEqual(await api("/health"), { ok: true });
});
