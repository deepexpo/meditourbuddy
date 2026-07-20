import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { eq } from "drizzle-orm";
import { parse } from "yaml";
import { db } from "../db.js";
import {
  accreditations,
  clinicProcedures,
  clinics,
  practitioners,
  procedures as proceduresTable,
} from "../schema.js";
import { procedures as procedureSeeds } from "./procedures.js";
import { clinicsSeedFileSchema } from "./types.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const seedFilePath = join(__dirname, "../../seed/clinics.yaml");

async function seedProcedures() {
  for (const procedure of procedureSeeds) {
    await db
      .insert(proceduresTable)
      .values(procedure)
      .onConflictDoUpdate({
        target: proceduresTable.code,
        set: {
          name: procedure.name,
          category: procedure.category,
          typicalVisits: procedure.typicalVisits,
          recoveryDaysOnsite: procedure.recoveryDaysOnsite,
        },
      });
  }
  console.log(`Seeded ${procedureSeeds.length} procedures`);
}

async function seedClinics() {
  const raw = readFileSync(seedFilePath, "utf-8");
  const parsed = clinicsSeedFileSchema.parse(parse(raw));

  const procedureIdByCode = new Map(
    (await db.select().from(proceduresTable)).map((p) => [p.code, p.id]),
  );

  for (const clinic of parsed.clinics) {
    await db.transaction(async (tx) => {
      const [clinicRow] = await tx
        .insert(clinics)
        .values({
          slug: clinic.slug,
          name: clinic.name,
          country: clinic.country,
          city: clinic.city,
          address: clinic.address,
          latitude: clinic.latitude != null ? String(clinic.latitude) : null,
          longitude:
            clinic.longitude != null ? String(clinic.longitude) : null,
          languages: clinic.languages,
          yearEstablished: clinic.yearEstablished ?? null,
          website: clinic.website ?? null,
        })
        .onConflictDoUpdate({
          target: clinics.slug,
          set: {
            name: clinic.name,
            country: clinic.country,
            city: clinic.city,
            address: clinic.address,
            latitude:
              clinic.latitude != null ? String(clinic.latitude) : null,
            longitude:
              clinic.longitude != null ? String(clinic.longitude) : null,
            languages: clinic.languages,
            yearEstablished: clinic.yearEstablished ?? null,
            website: clinic.website ?? null,
            updatedAt: new Date(),
          },
        })
        .returning();

      const clinicId = clinicRow!.id;

      await tx
        .delete(accreditations)
        .where(eq(accreditations.clinicId, clinicId));
      if (clinic.accreditations.length > 0) {
        await tx.insert(accreditations).values(
          clinic.accreditations.map((a) => ({
            clinicId,
            body: a.body,
            referenceId: a.referenceId ?? null,
            validFrom: a.validFrom ?? null,
            validUntil: a.validUntil ?? null,
            sourceUrl: a.sourceUrl,
          })),
        );
      }

      await tx
        .delete(practitioners)
        .where(eq(practitioners.clinicId, clinicId));
      if (clinic.practitioners.length > 0) {
        await tx.insert(practitioners).values(
          clinic.practitioners.map((p) => ({
            clinicId,
            fullName: p.fullName,
            title: p.title,
            licenseNumber: p.licenseNumber ?? null,
            licenseCountry: p.licenseCountry,
            yearsExperience: p.yearsExperience ?? null,
            profileUrl: p.profileUrl ?? null,
          })),
        );
      }

      await tx
        .delete(clinicProcedures)
        .where(eq(clinicProcedures.clinicId, clinicId));
      if (clinic.procedures.length > 0) {
        await tx.insert(clinicProcedures).values(
          clinic.procedures.map((cp) => {
            const procedureId = procedureIdByCode.get(cp.procedureCode);
            if (!procedureId) {
              throw new Error(
                `Unknown procedure code "${cp.procedureCode}" for clinic "${clinic.slug}"`,
              );
            }
            return {
              clinicId,
              procedureId,
              priceMin: String(cp.priceMin),
              priceMax: String(cp.priceMax),
              currency: cp.currency,
              includes: cp.includes,
              lastVerified: cp.lastVerified,
            };
          }),
        );
      }
    });
  }

  console.log(`Seeded ${parsed.clinics.length} clinics`);
}

async function main() {
  await seedProcedures();
  await seedClinics();
  console.log("Seed complete.");
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(() => {
    process.exit();
  });
