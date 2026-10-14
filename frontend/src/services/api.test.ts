// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { CaseRecord } from "../types";

beforeEach(() => { vi.resetModules(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it.each(["timeout", "cancel"])("keeps %s active while reading the response body", async mode => {
  vi.useFakeTimers();
  let requestSignal: AbortSignal | undefined;
  let finishBody!: () => void;
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init: RequestInit) => {
    requestSignal = init.signal!;
    const body = new ReadableStream<Uint8Array>({ start(controller) {
      finishBody = () => { controller.enqueue(new TextEncoder().encode("{}")); controller.close(); };
      requestSignal!.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
    } });
    return new Response(body);
  }));
  const { json } = await import("./api");
  const controller = new AbortController();
  const verdict = json("/cases", { method: "POST", signal: controller.signal }).then(() => null, error => error);
  await vi.advanceTimersByTimeAsync(1);
  if (mode === "timeout") await vi.advanceTimersByTimeAsync(30000);
  else controller.abort();
  const aborted = requestSignal?.aborted;
  // End the body even when testing a broken implementation, avoiding hangs.
  if (!aborted) {
    finishBody();
  }
  await verdict;
  expect(aborted).toBe(true);
});

it("retains the normal request timeout after backend discovery", async () => {
  vi.useFakeTimers();
  let signal: AbortSignal | undefined;
  let complete!: () => void;
  const fetcher = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith("/health")) return new Response(JSON.stringify({ ok: true, service: "medray-v2" }));
    if (fetcher.mock.calls.length === 1) throw new TypeError("offline");
    signal = init.signal!;
    return new Promise<Response>((resolve, reject) => {
      complete = () => resolve(new Response("[]"));
      signal!.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    });
  });
  vi.stubGlobal("fetch", fetcher);
  const { json } = await import("./api");
  const verdict = json("/cases").then(() => null, error => error);
  await vi.advanceTimersByTimeAsync(6000);
  const prematurelyAborted = signal?.aborted;
  complete();
  await verdict;
  expect(prematurelyAborted).toBe(false);
});

it("discovers only a healthy MedRay backend", async () => {
  const fetcher = vi.fn(async (url: string) => {
    if (url.endsWith("/health")) return new Response(JSON.stringify({ ok: true, app: url.includes(":8766/") ? "MedRay v2" : "Unrelated service" }));
    if (url.includes(":8766/")) return new Response("[]");
    throw new TypeError("offline");
  });
  vi.stubGlobal("fetch", fetcher);
  const { json, imageUrl } = await import("./api");
  await expect(json("/cases")).resolves.toEqual([]);
  expect(imageUrl("synthetic.png")).toContain(":8766/api/image");
});

it("honors caller cancellation without discovering or retrying servers", async () => {
  const fetcher = vi.fn(async (_url: string, init: RequestInit) => {
    if (init.signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    return new Response("[]");
  });
  vi.stubGlobal("fetch", fetcher);
  const { json } = await import("./api");
  const controller = new AbortController();
  controller.abort();
  await expect(json("/cases", { signal: controller.signal })).rejects.toThrow(/cancel/i);
  expect(fetcher.mock.calls.length).toBeLessThanOrEqual(1);
});

it("stops backend discovery immediately when the caller cancels", async () => {
  let discoveryStarted!: () => void;
  const started = new Promise<void>(resolve => { discoveryStarted = resolve; });
  const fetcher = vi.fn((_url: string, init: RequestInit) => {
    if (fetcher.mock.calls.length === 1) return Promise.reject(new TypeError("offline"));
    discoveryStarted();
    return new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")), { once: true });
    });
  });
  vi.stubGlobal("fetch", fetcher);
  const { json } = await import("./api");
  const controller = new AbortController();
  const request = json("/cases", { signal: controller.signal });
  const verdict = request.then(() => null, error => error);
  await started;
  controller.abort();
  const error = await verdict;
  expect(fetcher.mock.calls[1][1]?.signal?.aborted).toBe(true);
  expect(error?.message).toMatch(/cancel/i);
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("checks the identity of the initial health response", async () => {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify({ ok: true, app: url.includes(":8766/") ? "MedRay v2" : "Unrelated service" })));
  vi.stubGlobal("fetch", fetcher);
  const { api } = await import("./api");
  await expect(api.health()).resolves.toMatchObject({ app: "MedRay v2" });
});

it("does not retry a failed mutation", async () => {
  const fetcher = vi.fn().mockRejectedValue(new TypeError("offline"));
  vi.stubGlobal("fetch", fetcher);
  const { json } = await import("./api");
  await expect(json("/cases", { method: "POST", body: "{}" })).rejects.toThrow(/not retried/i);
  expect(fetcher).toHaveBeenCalledOnce();
});

it("sends the loaded case revision and preserves conflict status without retrying", async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Case changed elsewhere" }), { status: 409 }));
  vi.stubGlobal("fetch", fetcher);
  const { api, ApiError } = await import("./api");
  const payload: CaseRecord = { case_id: "case", revision: 7, title: "synthetic", metadata: {}, annotations: [], chat_history: [], created_at: "test", updated_at: "test" };
  await expect(api.saveCase(payload)).rejects.toEqual(new ApiError("Case changed elsewhere", 409));
  expect(fetcher).toHaveBeenCalledOnce();
  expect(fetcher.mock.calls[0][1].headers["If-Match"]).toBe('"7"');
});
