import { z } from "zod";
import {
  accreditationBodyEnum,
  countryCodeEnum,
  currencyEnum,
} from "../schema.js";

const accreditationSeedSchema = z.object({
  body: z.enum(accreditationBodyEnum.enumValues),
  referenceId: z.string().nullable().optional(),
  validFrom: z.string().nullable().optional(),
  validUntil: z.string().nullable().optional(),
  sourceUrl: z.string().url(),
});

const practitionerSeedSchema = z.object({
  fullName: z.string(),
  title: z.string(),
  licenseNumber: z.string().nullable().optional(),
  licenseCountry: z.string(),
  yearsExperience: z.number().int().nullable().optional(),
  profileUrl: z.string().url().nullable().optional(),
});

const clinicProcedureSeedSchema = z.object({
  procedureCode: z.string(),
  priceMin: z.number(),
  priceMax: z.number(),
  currency: z.enum(currencyEnum.enumValues),
  includes: z.array(z.string()).default([]),
  lastVerified: z.string(),
});

const clinicSeedSchema = z.object({
  slug: z.string(),
  name: z.string(),
  country: z.enum(countryCodeEnum.enumValues),
  city: z.string(),
  address: z.string(),
  latitude: z.number().nullable().optional(),
  longitude: z.number().nullable().optional(),
  languages: z.array(z.string()),
  yearEstablished: z.number().int().nullable().optional(),
  website: z.string().url().nullable().optional(),
  accreditations: z.array(accreditationSeedSchema),
  practitioners: z.array(practitionerSeedSchema),
  procedures: z.array(clinicProcedureSeedSchema),
});

export const clinicsSeedFileSchema = z.object({
  clinics: z.array(clinicSeedSchema),
});

export type ClinicSeed = z.infer<typeof clinicSeedSchema>;
export type ClinicsSeedFile = z.infer<typeof clinicsSeedFileSchema>;
