import { describe, expect, it } from "vitest";
import { searchClinics } from "./search-clinics.js";

const baseInput = {
  language: "en",
  require_accreditation: true,
} as const;

describe("search_clinics", () => {
  it("answers the spec's demo query: accredited all-on-4 in Istanbul under $8K", async () => {
    const result = await searchClinics({
      ...baseInput,
      procedure_code: "IMPLANT_ALL_ON_4",
      country: "TR",
      max_budget_usd: 8000,
    });
    expect(
      result.clinics.some((c) => c.slug === "maltepe-dental-istanbul"),
    ).toBe(true);
    for (const clinic of result.clinics) {
      expect(clinic.country).toBe("TR");
      expect(clinic.accreditations.length).toBeGreaterThan(0);
      expect(clinic.price_range_usd?.min).toBeLessThanOrEqual(8000);
    }
  });

  it("never returns a clinic with zero accreditations when require_accreditation is true", async () => {
    const result = await searchClinics({
      ...baseInput,
      procedure_code: "IMPLANT_SINGLE",
    });
    for (const clinic of result.clinics) {
      expect(clinic.accreditations.length).toBeGreaterThan(0);
    }
  });

  it("filters by country", async () => {
    const result = await searchClinics({
      ...baseInput,
      procedure_code: "IMPLANT_SINGLE",
      country: "MX",
    });
    expect(result.clinics.every((c) => c.country === "MX")).toBe(true);
    expect(
      result.clinics.some((c) => c.slug === "sani-dental-group-los-algodones"),
    ).toBe(true);
  });

  it("returns an empty list (not an error) for an unknown procedure_code", async () => {
    const result = await searchClinics({
      ...baseInput,
      procedure_code: "NOT_A_REAL_CODE",
    });
    expect(result.clinics).toEqual([]);
    expect(result.disclaimer).toBeTruthy();
  });

  it("caps results at 10", async () => {
    const result = await searchClinics({
      ...baseInput,
      procedure_code: "IMPLANT_SINGLE",
    });
    expect(result.clinics.length).toBeLessThanOrEqual(10);
  });
});
