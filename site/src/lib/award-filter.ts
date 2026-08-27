import { projectPath } from "./paths";

export interface AwardFilter {
  venue: string;
  year: number;
}

export function awardFilterHref(base: string, venue: string, year: number): string {
  if (!/^[A-Z0-9-]+$/.test(venue) || !Number.isInteger(year)) {
    throw new Error("Invalid award filter");
  }
  const query = new URLSearchParams({ venue, year: String(year) });
  return `${projectPath(base, "awards")}?${query.toString()}#award-${venue}-${year}`;
}

export function parseAwardFilter(search: string): AwardFilter | null {
  const query = new URLSearchParams(search);
  const venue = query.get("venue");
  const rawYear = query.get("year");
  const year = rawYear == null ? Number.NaN : Number(rawYear);
  if (
    venue == null ||
    !/^[A-Z0-9-]+$/.test(venue) ||
    rawYear == null ||
    !/^\d{4}$/.test(rawYear) ||
    !Number.isInteger(year) ||
    year < 1900 ||
    year > 3000
  ) return null;
  return { venue, year };
}
