import { accreditations, clinics, db } from "@meditourbuddy/shared";
import { and, eq } from "drizzle-orm";
import { z } from "zod";
import { DISCLAIMER } from "../disclaimer.js";

const VERIFIABLE_BODIES = ["JCI", "GHA", "AACI"] as const;

export const verifyAccreditationInputSchema = {
  slug: z.string(),
  body: z.enum(VERIFIABLE_BODIES).optional(),
};

const statusSchema = z.enum(["verified", "expired", "unverifiable"]);

export const verifyAccreditationOutputSchema = {
  results: z.array(
    z.object({
      body: z.string(),
      status: statusSchema,
      source_url: z.string().nullable(),
      valid_until: z.string().nullable(),
      checked_at: z.string(),
    }),
  ),
  disclaimer: z.string(),
};

function statusFor(validUntil: string | null): "verified" | "expired" {
  if (!validUntil) return "verified";
  return new Date(validUntil).getTime() < Date.now() ? "expired" : "verified";
}

export async function verifyAccreditation(input: {
  slug: string;
  body?: (typeof VERIFIABLE_BODIES)[number];
}) {
  const [clinic] = await db
    .select()
    .from(clinics)
    .where(eq(clinics.slug, input.slug));

  if (!clinic) {
    throw new Error(`Clinic not found: ${input.slug}`);
  }

  const rows = await db
    .select()
    .from(accreditations)
    .where(
      and(
        eq(accreditations.clinicId, clinic.id),
        input.body ? eq(accreditations.body, input.body) : undefined,
      ),
    );

  const checkedAt = new Date().toISOString();

  const results =
    rows.length > 0
      ? rows.map((row) => ({
          body: row.body,
          status: statusFor(row.validUntil),
          source_url: row.sourceUrl,
          valid_until: row.validUntil,
          checked_at: checkedAt,
        }))
      : input.body
        ? [
            {
              body: input.body,
              status: "unverifiable" as const,
              source_url: null,
              valid_until: null,
              checked_at: checkedAt,
            },
          ]
        : [];

  return { results, disclaimer: DISCLAIMER };
}
