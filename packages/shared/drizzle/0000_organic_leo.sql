DO $$ BEGIN
 CREATE TYPE "public"."accreditation_body" AS ENUM('JCI', 'GHA', 'AACI', 'ISO_9001', 'NATIONAL');
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 CREATE TYPE "public"."country_code" AS ENUM('TR', 'MX');
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 CREATE TYPE "public"."currency_code" AS ENUM('USD', 'EUR', 'CAD', 'MXN', 'TRY');
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 CREATE TYPE "public"."procedure_category" AS ENUM('implant', 'restorative', 'cosmetic', 'surgical');
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 CREATE TYPE "public"."review_source" AS ENUM('google', 'whatclinic');
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "accreditations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"clinic_id" uuid NOT NULL,
	"body" "accreditation_body" NOT NULL,
	"reference_id" text,
	"valid_from" date,
	"valid_until" date,
	"source_url" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "clinic_procedures" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"clinic_id" uuid NOT NULL,
	"procedure_id" uuid NOT NULL,
	"price_min" numeric(10, 2) NOT NULL,
	"price_max" numeric(10, 2) NOT NULL,
	"currency" "currency_code" NOT NULL,
	"includes" text[] DEFAULT '{}'::text[] NOT NULL,
	"last_verified" date NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "clinics" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"slug" text NOT NULL,
	"name" text NOT NULL,
	"country" "country_code" NOT NULL,
	"city" text NOT NULL,
	"address" text NOT NULL,
	"latitude" numeric(9, 6),
	"longitude" numeric(9, 6),
	"languages" text[] DEFAULT '{}'::text[] NOT NULL,
	"year_established" integer,
	"website" text,
	"verified_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "clinics_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "practitioners" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"clinic_id" uuid NOT NULL,
	"full_name" text NOT NULL,
	"title" text NOT NULL,
	"license_number" text,
	"license_country" text NOT NULL,
	"years_experience" integer,
	"profile_url" text
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "procedures" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"code" text NOT NULL,
	"name" text NOT NULL,
	"category" "procedure_category" NOT NULL,
	"typical_visits" integer NOT NULL,
	"recovery_days_onsite" integer NOT NULL,
	CONSTRAINT "procedures_code_unique" UNIQUE("code")
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "reviews_summary" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"clinic_id" uuid NOT NULL,
	"source" "review_source" NOT NULL,
	"rating" numeric(2, 1) NOT NULL,
	"review_count" integer NOT NULL,
	"fetched_at" timestamp with time zone NOT NULL
);
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "accreditations" ADD CONSTRAINT "accreditations_clinic_id_clinics_id_fk" FOREIGN KEY ("clinic_id") REFERENCES "public"."clinics"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "clinic_procedures" ADD CONSTRAINT "clinic_procedures_clinic_id_clinics_id_fk" FOREIGN KEY ("clinic_id") REFERENCES "public"."clinics"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "clinic_procedures" ADD CONSTRAINT "clinic_procedures_procedure_id_procedures_id_fk" FOREIGN KEY ("procedure_id") REFERENCES "public"."procedures"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "practitioners" ADD CONSTRAINT "practitioners_clinic_id_clinics_id_fk" FOREIGN KEY ("clinic_id") REFERENCES "public"."clinics"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "reviews_summary" ADD CONSTRAINT "reviews_summary_clinic_id_clinics_id_fk" FOREIGN KEY ("clinic_id") REFERENCES "public"."clinics"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
