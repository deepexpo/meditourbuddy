const STALE_AFTER_DAYS = 90;

export function isStale(lastVerified: string): boolean {
  const verifiedAt = new Date(lastVerified).getTime();
  const ageDays = (Date.now() - verifiedAt) / (1000 * 60 * 60 * 24);
  return ageDays > STALE_AFTER_DAYS;
}

// Strongest-to-weakest. Index = rank (lower is stronger); unlisted body -> weakest.
export const ACCREDITATION_RANK = [
  "JCI",
  "GHA",
  "AACI",
  "ISO_9001",
  "NATIONAL",
] as const;

export function accreditationRank(bodies: readonly string[]): number {
  if (bodies.length === 0) return ACCREDITATION_RANK.length;
  return Math.min(
    ...bodies.map((b) => {
      const idx = ACCREDITATION_RANK.indexOf(
        b as (typeof ACCREDITATION_RANK)[number],
      );
      return idx === -1 ? ACCREDITATION_RANK.length : idx;
    }),
  );
}
