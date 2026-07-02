import { relations, sql } from "drizzle-orm";
import {
  date,
  integer,
  numeric,
  pgEnum,
  pgTable,
  text,
  timestamp,
  uuid,
} from "drizzle-orm/pg-core";

export const countryCodeEnum = pgEnum("country_code", ["TR", "MX"]);

export const accreditationBodyEnum = pgEnum("accreditation_body", [
  "JCI",
  "GHA",
  "AACI",
  "ISO_9001",
  "NATIONAL",
]);

export const procedureCategoryEnum = pgEnum("procedure_category", [
  "implant",
  "restorative",
  "cosmetic",
  "surgical",
]);

export const currencyEnum = pgEnum("currency_code", [
  "USD",
  "EUR",
  "CAD",
  "MXN",
  "TRY",
]);

export const reviewSourceEnum = pgEnum("review_source", [
  "google",
  "whatclinic",
]);

export const clinics = pgTable("clinics", {
  id: uuid("id").primaryKey().default(sql`gen_random_uuid()`),
  slug: text("slug").notNull().unique(),
  name: text("name").notNull(),
  country: countryCodeEnum("country").notNull(),
  city: text("city").notNull(),
  address: text("address").notNull(),
  latitude: numeric("latitude", { precision: 9, scale: 6 }),
  longitude: numeric("longitude", { precision: 9, scale: 6 }),
  languages: text("languages").array().notNull().default(sql`'{}'::text[]`),
  yearEstablished: integer("year_established"),
  website: text("website"),
  verifiedAt: timestamp("verified_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const accreditations = pgTable("accreditations", {
  id: uuid("id").primaryKey().default(sql`gen_random_uuid()`),
  clinicId: uuid("clinic_id")
    .notNull()
    .references(() => clinics.id, { onDelete: "cascade" }),
  body: accreditationBodyEnum("body").notNull(),
  referenceId: text("reference_id"),
  validFrom: date("valid_from"),
  validUntil: date("valid_until"),
  sourceUrl: text("source_url").notNull(),
});

export const practitioners = pgTable("practitioners", {
  id: uuid("id").primaryKey().default(sql`gen_random_uuid()`),
  clinicId: uuid("clinic_id")
    .notNull()
    .references(() => clinics.id, { onDelete: "cascade" }),
  fullName: text("full_name").notNull(),
  title: text("title").notNull(),
  licenseNumber: text("license_number"),
  licenseCountry: text("license_country").notNull(),
  yearsExperience: integer("years_experience"),
  profileUrl: text("profile_url"),
});

export const procedures = pgTable("procedures", {
  id: uuid("id").primaryKey().default(sql`gen_random_uuid()`),
  code: text("code").notNull().unique(),
  name: text("name").notNull(),
  category: procedureCategoryEnum("category").notNull(),
  typicalVisits: integer("typical_visits").notNull(),
  recoveryDaysOnsite: integer("recovery_days_onsite").notNull(),
});

export const clinicProcedures = pgTable("clinic_procedures", {
  id: uuid("id").primaryKey().default(sql`gen_random_uuid()`),
  clinicId: uuid("clinic_id")
    .notNull()
    .references(() => clinics.id, { onDelete: "cascade" }),
  procedureId: uuid("procedure_id")
    .notNull()
    .references(() => procedures.id, { onDelete: "cascade" }),
  priceMin: numeric("price_min", { precision: 10, scale: 2 }).notNull(),
  priceMax: numeric("price_max", { precision: 10, scale: 2 }).notNull(),
  currency: currencyEnum("currency").notNull(),
  includes: text("includes").array().notNull().default(sql`'{}'::text[]`),
  lastVerified: date("last_verified").notNull(),
});

// Phase 2 — aggregated review scores only, no individual review scraping.
export const reviewsSummary = pgTable("reviews_summary", {
  id: uuid("id").primaryKey().default(sql`gen_random_uuid()`),
  clinicId: uuid("clinic_id")
    .notNull()
    .references(() => clinics.id, { onDelete: "cascade" }),
  source: reviewSourceEnum("source").notNull(),
  rating: numeric("rating", { precision: 2, scale: 1 }).notNull(),
  reviewCount: integer("review_count").notNull(),
  fetchedAt: timestamp("fetched_at", { withTimezone: true }).notNull(),
});

export const clinicsRelations = relations(clinics, ({ many }) => ({
  accreditations: many(accreditations),
  practitioners: many(practitioners),
  procedures: many(clinicProcedures),
  reviews: many(reviewsSummary),
}));

export const accreditationsRelations = relations(accreditations, ({ one }) => ({
  clinic: one(clinics, {
    fields: [accreditations.clinicId],
    references: [clinics.id],
  }),
}));

export const practitionersRelations = relations(practitioners, ({ one }) => ({
  clinic: one(clinics, {
    fields: [practitioners.clinicId],
    references: [clinics.id],
  }),
}));

export const proceduresRelations = relations(procedures, ({ many }) => ({
  clinics: many(clinicProcedures),
}));

export const clinicProceduresRelations = relations(
  clinicProcedures,
  ({ one }) => ({
    clinic: one(clinics, {
      fields: [clinicProcedures.clinicId],
      references: [clinics.id],
    }),
    procedure: one(procedures, {
      fields: [clinicProcedures.procedureId],
      references: [procedures.id],
    }),
  }),
);

export const reviewsSummaryRelations = relations(reviewsSummary, ({ one }) => ({
  clinic: one(clinics, {
    fields: [reviewsSummary.clinicId],
    references: [clinics.id],
  }),
}));
