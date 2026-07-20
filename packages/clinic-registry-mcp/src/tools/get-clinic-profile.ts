import { db } from "@meditourbuddy/shared";
import { z } from "zod";
import { DISCLAIMER } from "../disclaimer.js";
import { isStale } from "../util.js";

export const getClinicProfileInputSchema = {
  slug: z.string(),
};

export const getClinicProfileOutputSchema = {
  clinic: z.object({
    id: z.string(),
    slug: z.string(),
    name: z.string(),
    country: z.string(),
    city: z.string(),
    address: z.string(),
    latitude: z.number().nullable(),
    longitude: z.number().nullable(),
    languages: z.array(z.string()),
    year_established: z.number().nullable(),
    website: z.string().nullable(),
    verified_at: z.string().nullable(),
    created_at: z.string(),
    updated_at: z.string(),
  }),
  accreditations: z.array(
    z.object({
      body: z.string(),
      reference_id: z.string().nullable(),
      valid_until: z.string().nullable(),
      source_url: z.string(),
    }),
  ),
  practitioners: z.array(
    z.object({
      full_name: z.string(),
      title: z.string(),
      years_experience: z.number().nullable(),
    }),
  ),
  procedures: z.array(
    z.object({
      code: z.string(),
      name: z.string(),
      price_min: z.number(),
      price_max: z.number(),
      currency: z.string(),
      includes: z.array(z.string()),
      last_verified: z.string(),
      stale: z.boolean(),
    }),
  ),
  disclaimer: z.string(),
};

export async function getClinicProfile(input: { slug: string }) {
  const clinic = await db.query.clinics.findFirst({
    where: (clinics, { eq }) => eq(clinics.slug, input.slug),
    with: {
      accreditations: true,
      practitioners: true,
      procedures: { with: { procedure: true } },
    },
  });

  if (!clinic) {
    throw new Error(`Clinic not found: ${input.slug}`);
  }

  return {
    clinic: {
      id: clinic.id,
      slug: clinic.slug,
      name: clinic.name,
      country: clinic.country,
      city: clinic.city,
      address: clinic.address,
      latitude: clinic.latitude !== null ? Number(clinic.latitude) : null,
      longitude: clinic.longitude !== null ? Number(clinic.longitude) : null,
      languages: clinic.languages,
      year_established: clinic.yearEstablished,
      website: clinic.website,
      verified_at: clinic.verifiedAt ? clinic.verifiedAt.toISOString() : null,
      created_at: clinic.createdAt.toISOString(),
      updated_at: clinic.updatedAt.toISOString(),
    },
    accreditations: clinic.accreditations.map((a) => ({
      body: a.body,
      reference_id: a.referenceId,
      valid_until: a.validUntil,
      source_url: a.sourceUrl,
    })),
    practitioners: clinic.practitioners.map((p) => ({
      full_name: p.fullName,
      title: p.title,
      years_experience: p.yearsExperience,
    })),
    procedures: clinic.procedures.map((cp) => ({
      code: cp.procedure.code,
      name: cp.procedure.name,
      price_min: Number(cp.priceMin),
      price_max: Number(cp.priceMax),
      currency: cp.currency,
      includes: cp.includes,
      last_verified: cp.lastVerified,
      stale: isStale(cp.lastVerified),
    })),
    disclaimer: DISCLAIMER,
  };
}
