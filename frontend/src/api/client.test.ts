import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearAccessCode,
  getAccessCode,
  setAccessCode,
  validateAccessCode,
} from "./client";

describe("access code storage", () => {
  beforeEach(() => {
    sessionStorage.clear();
    clearAccessCode();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stores nothing when the server rejects the code", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 401 })));
    expect(await validateAccessCode("wrong")).toBe(false);
    expect(getAccessCode()).toBe("");
  });

  it("stores nothing when the request fails outright", async () => {
    // The original bug: the code was saved before validation, so a CORS failure or a
    // network blip showed "not recognised" while leaving the code behind — and a
    // refresh then walked straight past the gate.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    expect(await validateAccessCode("blocked-by-cors")).toBe(false);
    expect(getAccessCode()).toBe("");
  });

  it("does not send the stored code when validating a candidate", async () => {
    setAccessCode("previously-stored");
    const fetchMock = vi.fn(
      async (_url: string, _init?: RequestInit) => new Response("[]", { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await validateAccessCode("the-candidate");

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers["X-Access-Code"]).toBe("the-candidate");
  });

  it("reports success for an accepted code, and only then is it stored", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("[]", { status: 200 })));
    expect(await validateAccessCode("right")).toBe(true);
    // validateAccessCode itself never writes: persisting stays the caller's decision.
    expect(getAccessCode()).toBe("");
    setAccessCode("right");
    expect(getAccessCode()).toBe("right");
  });

  it("survives sessionStorage being unavailable", () => {
    vi.stubGlobal("sessionStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    });
    expect(getAccessCode()).toBe("");
    expect(() => setAccessCode("x")).not.toThrow();
  });
});
