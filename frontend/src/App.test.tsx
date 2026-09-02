import { describe, expect, it } from "vitest";

describe("frontend smoke", () => {
  it("has a runnable test environment", () => {
    expect("MedRay v2").toContain("MedRay");
  });
});
