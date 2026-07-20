import {
  clinicProcedures,
  clinics,
  countryCodeEnum,
  db,
  FX_AS_OF,
  FX_RATES,
  procedures,
  toUsd,
} from "@meditourbuddy/shared";
import { and, eq } from "drizzle-orm";
import { z } from "zod";
import { DISCLAIMER } from "../disclaimer.js";
import { isStale } from "../util.js";

export const compareProceduresInputSchema = {
  procedure_code: z.string(),
  canadian_quote_cad: z.number().positive().optional(),
  country: z.enum(countryCodeEnum.enumValues).optional(),
};

export const compareProceduresOutputSchema = {
  procedure: z.object({
    code: z.string(),
    name: z.string(),
    typical_visits: z.number(),
    recovery_days_onsite: z.number(),
  }),
  options: z.array(
    z.object({
      clinic_slug: z.string(),
      clinic_name: z.string(),
      price_range_usd: z.object({
        min: z.number(),
        max: z.number(),
        stale: z.boolean(),
      }),
      savings_vs_quote_pct: z.number().nullable(),
    }),
  ),
  fx_rate_used: z.object({ cad_usd: z.number(), as_of: z.string() }),
  disclaimer: z.string(),
};

export async function compareProcedures(input: {
  procedure_code: string;
  canadian_quote_cad?: number;
  country?: (typeof countryCodeEnum.enumValues)[number];
}) {
  const [procedure] = await db
    .select()
    .from(procedures)
    .where(eq(procedures.code, input.procedure_code));

  if (!procedure) {
    throw new Error(`Unknown procedure_code: ${input.procedure_code}`);
  }

  const rows = await db
    .select({
      clinicSlug: clinics.slug,
      clinicName: clinics.name,
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
      ),
    );

  const quoteUsd =
    input.canadian_quote_cad !== undefined
      ? toUsd(input.canadian_quote_cad, "CAD")
      : null;

  const options = rows.map((row) => {
    const minUsd = toUsd(Number(row.priceMin), row.currency);
    const maxUsd = toUsd(Number(row.priceMax), row.currency);
    const midpointUsd = (minUsd + maxUsd) / 2;
    return {
      clinic_slug: row.clinicSlug,
      clinic_name: row.clinicName,
      price_range_usd: {
        min: minUsd,
        max: maxUsd,
        stale: isStale(row.lastVerified),
      },
      savings_vs_quote_pct:
        quoteUsd !== null ? ((quoteUsd - midpointUsd) / quoteUsd) * 100 : null,
    };
  });

  options.sort((a, b) => a.price_range_usd.min - b.price_range_usd.min);

  return {
    procedure: {
      code: procedure.code,
      name: procedure.name,
      typical_visits: procedure.typicalVisits,
      recovery_days_onsite: procedure.recoveryDaysOnsite,
    },
    options,
    fx_rate_used: { cad_usd: FX_RATES.CAD, as_of: FX_AS_OF },
    disclaimer: DISCLAIMER,
  };
}
