import { FX_AS_OF, FX_RATES } from "@meditourbuddy/shared";
import { describe, expect, it } from "vitest";
import { compareProcedures } from "./compare-procedures.js";

describe("compare_procedures", () => {
  it("returns options for every clinic that has priced the procedure, sorted ascending", async () => {
    const result = await compareProcedures({ procedure_code: "IMPLANT_SINGLE" });
    expect(result.procedure.code).toBe("IMPLANT_SINGLE");
    expect(result.options.length).toBeGreaterThanOrEqual(3);
    const prices = result.options.map((o) => o.price_range_usd.min);
    expect(prices).toEqual([...prices].sort((a, b) => a - b));
  });

  it("uses the static FX table", async () => {
    const result = await compareProcedures({ procedure_code: "IMPLANT_SINGLE" });
    expect(result.fx_rate_used).toEqual({
      cad_usd: FX_RATES.CAD,
      as_of: FX_AS_OF,
    });
  });

  it("savings_vs_quote_pct is null without a quote, numeric with one", async () => {
    const withoutQuote = await compareProcedures({
      procedure_code: "IMPLANT_SINGLE",
    });
    for (const o of withoutQuote.options) {
      expect(o.savings_vs_quote_pct).toBeNull();
    }

    const withQuote = await compareProcedures({
      procedure_code: "IMPLANT_SINGLE",
      canadian_quote_cad: 3000,
    });
    for (const o of withQuote.options) {
      expect(typeof o.savings_vs_quote_pct).toBe("number");
    }
  });

  it("throws for an unknown procedure_code", async () => {
    await expect(
      compareProcedures({ procedure_code: "NOT_A_REAL_CODE" }),
    ).rejects.toThrow();
  });
});
