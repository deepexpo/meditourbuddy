import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "../../..");

export default function setup() {
  if (!process.env.DATABASE_URL) {
    throw new Error(
      "DATABASE_URL is not set. Start a test Postgres (docker compose up -d --wait, " +
        "or see .env.test.example) and export DATABASE_URL before running tests.",
    );
  }

  const run = (command: string) =>
    execSync(command, { cwd: repoRoot, stdio: "inherit", env: process.env });

  run("pnpm --filter @meditourbuddy/shared exec drizzle-kit push --force");
  run("pnpm --filter @meditourbuddy/shared db:seed");
}
