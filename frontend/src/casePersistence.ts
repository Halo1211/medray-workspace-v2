import type { CaseRecord } from "./types";

/** A single editor's writes share a queue and the revisions it has committed. */
export class CaseSaveSession {
  private pending: Promise<void> = Promise.resolve();
  private revisions = new Set<number>();
  private latestRevision: number | undefined;
  private failure: unknown = null;

  constructor(private readonly persist: (record: CaseRecord) => Promise<CaseRecord>) {}

  get failed() { return this.failure !== null; }

  save(record: CaseRecord): Promise<CaseRecord> {
    const result = this.pending.then(async () => {
      if (this.failure !== null) throw this.failure;
      const revision = record.revision;
      const followsOwnSave = revision !== undefined && this.revisions.has(revision);
      const saved = await this.persist({ ...record, revision: followsOwnSave ? this.latestRevision : revision });
      if (!followsOwnSave) this.revisions.clear();
      if (revision !== undefined) this.revisions.add(revision);
      if (saved.revision !== undefined) this.revisions.add(saved.revision);
      this.latestRevision = saved.revision;
      return saved;
    }).catch(error => { this.failure = error; throw error; });
    this.pending = result.then(() => undefined, () => undefined);
    return result;
  }

  async idle(): Promise<void> {
    let pending: Promise<void>;
    do { pending = this.pending; await pending; } while (pending !== this.pending);
    if (this.failure !== null) throw this.failure;
  }
}
