import { db, procedureCategoryEnum, procedures } from "@meditourbuddy/shared";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { DISCLAIMER } from "../disclaimer.js";

export const listProceduresInputSchema = {
  category: z.enum(procedureCategoryEnum.enumValues).optional(),
};

export const listProceduresOutputSchema = {
  procedures: z.array(
    z.object({
      code: z.string(),
      name: z.string(),
      category: z.enum(procedureCategoryEnum.enumValues),
      typical_visits: z.number(),
      recovery_days_onsite: z.number(),
    }),
  ),
  disclaimer: z.string(),
};

export async function listProcedures(input: {
  category?: (typeof procedureCategoryEnum.enumValues)[number];
}) {
  const rows = input.category
    ? await db
        .select()
        .from(procedures)
        .where(eq(procedures.category, input.category))
    : await db.select().from(procedures);

  return {
    procedures: rows.map((p) => ({
      code: p.code,
      name: p.name,
      category: p.category,
      typical_visits: p.typicalVisits,
      recovery_days_onsite: p.recoveryDaysOnsite,
    })),
    disclaimer: DISCLAIMER,
  };
}
