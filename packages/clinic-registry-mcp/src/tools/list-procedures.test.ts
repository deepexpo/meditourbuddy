import { describe, expect, it } from "vitest";
import { listProcedures } from "./list-procedures.js";

describe("list_procedures", () => {
  it("returns all 12 seeded procedures when no category is given", async () => {
    const result = await listProcedures({});
    expect(result.procedures).toHaveLength(12);
  });

  it("filters by category", async () => {
    const result = await listProcedures({ category: "implant" });
    expect(result.procedures.map((p) => p.code).sort()).toEqual(
      ["IMPLANT_ALL_ON_4", "IMPLANT_ALL_ON_6", "IMPLANT_SINGLE"].sort(),
    );
    for (const p of result.procedures) {
      expect(p.category).toBe("implant");
    }
  });

  it("includes the disclaimer", async () => {
    const result = await listProcedures({});
    expect(result.disclaimer).toMatch(/not medical advice/i);
  });
});
