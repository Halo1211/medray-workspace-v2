import { expect, it, vi } from "vitest";
import { CaseSaveSession } from "./casePersistence";
import type { CaseRecord } from "./types";

const record = (revision: number, title = "synthetic"): CaseRecord => ({
  case_id: "case", revision, title, metadata: {}, annotations: [], chat_history: [], created_at: "test", updated_at: "test",
});

it("serializes rapid edits and uses revisions acknowledged by this editor", async () => {
  let finish!: (value: CaseRecord) => void;
  const persist = vi.fn().mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }))
    .mockImplementation(async (value: CaseRecord) => ({ ...value, revision: value.revision! + 1 }));
  const session = new CaseSaveSession(persist);
  const first = session.save(record(1, "first"));
  const second = session.save(record(1, "second"));
  await Promise.resolve();
  expect(persist).toHaveBeenCalledOnce();
  finish(record(2, "first"));
  await first;
  expect((await second).revision).toBe(3);
  expect(persist.mock.calls[1][0]).toMatchObject({ title: "second", revision: 2 });
});

it("stops queued writes after a conflict and blocks export until recovery", async () => {
  const conflict = new Error("Case changed elsewhere");
  const persist = vi.fn().mockRejectedValue(conflict);
  const session = new CaseSaveSession(persist);
  const first = session.save(record(1));
  const second = session.save(record(1));
  await expect(first).rejects.toBe(conflict);
  await expect(second).rejects.toBe(conflict);
  await expect(session.idle()).rejects.toBe(conflict);
  expect(persist).toHaveBeenCalledOnce();
});

it("does not promote a revision this editor never acknowledged", async () => {
  const persist = vi.fn(async (value: CaseRecord) => ({ ...value, revision: value.revision! + 1 }));
  const session = new CaseSaveSession(persist);
  await session.save(record(1));
  await session.save(record(10));
  await session.save(record(1));
  expect(persist.mock.calls[2][0].revision).toBe(1);
});
