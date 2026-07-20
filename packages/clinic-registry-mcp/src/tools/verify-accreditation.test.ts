import { accreditations, clinics, db } from "@meditourbuddy/shared";
import { eq } from "drizzle-orm";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { verifyAccreditation } from "./verify-accreditation.js";

describe("verify_accreditation", () => {
  it("returns verified for a real accreditation with no body filter", async () => {
    const result = await verifyAccreditation({
      slug: "sani-dental-group-los-algodones",
    });
    expect(result.results).toHaveLength(1);
    expect(result.results[0]?.body).toBe("NATIONAL");
    expect(result.results[0]?.status).toBe("verified");
    expect(result.results[0]?.source_url).toBeTruthy();
  });

  it("returns unverifiable when the clinic has no row for the requested body", async () => {
    const result = await verifyAccreditation({
      slug: "acibadem-maslak-istanbul",
      body: "GHA",
    });
    expect(result.results).toEqual([
      {
        body: "GHA",
        status: "unverifiable",
        source_url: null,
        valid_until: null,
        checked_at: expect.any(String),
      },
    ]);
  });

  it("throws for an unknown slug", async () => {
    await expect(
      verifyAccreditation({ slug: "does-not-exist" }),
    ).rejects.toThrow();
  });

  describe("expired accreditation", () => {
    let tempAccreditationId: string;

    beforeAll(async () => {
      const [clinic] = await db
        .select()
        .from(clinics)
        .where(eq(clinics.slug, "acibadem-maslak-istanbul"));
      if (!clinic) throw new Error("fixture clinic not found");

      const [inserted] = await db
        .insert(accreditations)
        .values({
          clinicId: clinic.id,
          body: "AACI",
          sourceUrl: "https://example.com/expired-test-fixture",
          validUntil: "2000-01-01",
        })
        .returning();
      tempAccreditationId = inserted!.id;
    });

    afterAll(async () => {
      await db
        .delete(accreditations)
        .where(eq(accreditations.id, tempAccreditationId));
    });

    it("returns expired for a past valid_until", async () => {
      const result = await verifyAccreditation({
        slug: "acibadem-maslak-istanbul",
        body: "AACI",
      });
      expect(result.results).toHaveLength(1);
      expect(result.results[0]?.status).toBe("expired");
      expect(result.results[0]?.valid_until).toBe("2000-01-01");
    });
  });
});
