import {
  accreditations,
  clinicProcedures,
  clinics,
  countryCodeEnum,
  db,
  procedures,
  practitioners,
  toUsd,
} from "@meditourbuddy/shared";
import { and, arrayContains, eq, inArray } from "drizzle-orm";
import { z } from "zod";
import { DISCLAIMER } from "../disclaimer.js";
import { accreditationRank, isStale } from "../util.js";

export const searchClinicsInputSchema = {
  procedure_code: z.string(),
  country: z.enum(countryCodeEnum.enumValues).optional(),
  max_budget_usd: z.number().positive().optional(),
  language: z.string().default("en"),
  require_accreditation: z.boolean().default(true),
};

const clinicResultSchema = z.object({
  slug: z.string(),
  name: z.string(),
  city: z.string(),
  country: z.enum(countryCodeEnum.enumValues),
  accreditations: z.array(z.string()),
  price_range_usd: z
    .object({ min: z.number(), max: z.number(), stale: z.boolean() })
    .nullable(),
  practitioner_count: z.number(),
  verified_at: z.string().nullable(),
});

export const searchClinicsOutputSchema = {
  clinics: z.array(clinicResultSchema),
  disclaimer: z.string(),
};

export async function searchClinics(input: {
  procedure_code: string;
  country?: (typeof countryCodeEnum.enumValues)[number];
  max_budget_usd?: number;
  language: string;
  require_accreditation: boolean;
}) {
  const [procedure] = await db
    .select()
    .from(procedures)
    .where(eq(procedures.code, input.procedure_code));

  if (!procedure) {
    return { clinics: [], disclaimer: DISCLAIMER };
  }

  const matches = await db
    .select({
      clinic: clinics,
      priceMin: clinicProcedures.priceMin,
      priceMax: clinicProcedures.priceMax,
      currency: clinicProcedures.currency,
      lastVerified: clinicProcedures.lastVerified,
    })
    .from(clinicProcedures)
    .innerJoin(clinics, eq(clinicProcedures.clinicId, clinics.id))
    .where(
      and(
        eq(clinicProcedures.procedureId, procedure.id),
        input.country ? eq(clinics.country, input.country) : undefined,
        arrayContains(clinics.languages, [input.language]),
      ),
    );

  if (matches.length === 0) {
    return { clinics: [], disclaimer: DISCLAIMER };
  }

  const clinicIds = [...new Set(matches.map((m) => m.clinic.id))];

  const accreditationRows = await db
    .select()
    .from(accreditations)
    .where(inArray(accreditations.clinicId, clinicIds));
  const accreditationsByClinic = new Map<string, string[]>();
  for (const row of accreditationRows) {
    const list = accreditationsByClinic.get(row.clinicId) ?? [];
    list.push(row.body);
    accreditationsByClinic.set(row.clinicId, list);
  }

  const practitionerRows = await db
    .select({ clinicId: practitioners.clinicId })
    .from(practitioners)
    .where(inArray(practitioners.clinicId, clinicIds));
  const practitionerCountByClinic = new Map<string, number>();
  for (const row of practitionerRows) {
    practitionerCountByClinic.set(
      row.clinicId,
      (practitionerCountByClinic.get(row.clinicId) ?? 0) + 1,
    );
  }

  const priceByClinic = new Map<
    string,
    { min: number; max: number; stale: boolean }
  >();
  for (const m of matches) {
    const minUsd = toUsd(Number(m.priceMin), m.currency);
    const maxUsd = toUsd(Number(m.priceMax), m.currency);
    const stale = isStale(m.lastVerified);
    const existing = priceByClinic.get(m.clinic.id);
    priceByClinic.set(m.clinic.id, {
      min: existing ? Math.min(existing.min, minUsd) : minUsd,
      max: existing ? Math.max(existing.max, maxUsd) : maxUsd,
      stale: existing ? existing.stale || stale : stale,
    });
  }

  const uniqueClinics = new Map(matches.map((m) => [m.clinic.id, m.clinic]));

  let results = [...uniqueClinics.values()].map((clinic) => {
    const price = priceByClinic.get(clinic.id) ?? null;
    const clinicAccreditations = accreditationsByClinic.get(clinic.id) ?? [];
    return {
      slug: clinic.slug,
      name: clinic.name,
      city: clinic.city,
      country: clinic.country,
      accreditations: clinicAccreditations,
      price_range_usd: price,
      practitioner_count: practitionerCountByClinic.get(clinic.id) ?? 0,
      verified_at: clinic.verifiedAt ? clinic.verifiedAt.toISOString() : null,
      _rank: accreditationRank(clinicAccreditations),
    };
  });

  if (input.require_accreditation) {
    results = results.filter((r) => r.accreditations.length > 0);
  }

  if (input.max_budget_usd !== undefined) {
    const budget = input.max_budget_usd;
    results = results.filter(
      (r) => r.price_range_usd !== null && r.price_range_usd.min <= budget,
    );
  }

  results.sort((a, b) => {
    if (a._rank !== b._rank) return a._rank - b._rank;
    const aPrice = a.price_range_usd?.min ?? Infinity;
    const bPrice = b.price_range_usd?.min ?? Infinity;
    return aPrice - bPrice;
  });

  return {
    clinics: results.slice(0, 10).map(({ _rank, ...rest }) => rest),
    disclaimer: DISCLAIMER,
  };
}
