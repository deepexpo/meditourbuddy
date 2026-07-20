import { describe, expect, it } from "vitest";
import { getClinicProfile } from "./get-clinic-profile.js";

describe("get_clinic_profile", () => {
  it("returns full nested detail for a known slug", async () => {
    const result = await getClinicProfile({ slug: "maltepe-dental-istanbul" });
    expect(result.clinic.slug).toBe("maltepe-dental-istanbul");
    expect(result.practitioners.length).toBeGreaterThan(0);
    expect(result.procedures.length).toBeGreaterThan(0);
    expect(result.disclaimer).toBeTruthy();
  });

  it("every accreditation row carries a non-empty source_url", async () => {
    const result = await getClinicProfile({ slug: "acibadem-maslak-istanbul" });
    expect(result.accreditations.length).toBeGreaterThan(0);
    for (const a of result.accreditations) {
      expect(a.source_url).toBeTruthy();
    }
  });

  it("throws for an unknown slug", async () => {
    await expect(
      getClinicProfile({ slug: "does-not-exist" }),
    ).rejects.toThrow();
  });
});
