import { projectPath } from "./paths";

export interface AdvanceFilter {
  venue: string;
  year: number;
}

function validVenueYear(venue: string, year: number): boolean {
  return /^[A-Z0-9-]+$/.test(venue) && Number.isInteger(year) && year >= 1900 && year <= 3000;
}

export function advanceFilterHref(base: string, venue: string, year: number): string {
  if (!validVenueYear(venue, year)) throw new Error("Invalid advance filter");
  const query = new URLSearchParams({ venue, year: String(year) });
  return `${projectPath(base, "advances")}?${query.toString()}#advance-${venue}-${year}`;
}

export function parseAdvanceFilter(search: string): AdvanceFilter | null {
  const query = new URLSearchParams(search);
  const venue = query.get("venue");
  const rawYear = query.get("year");
  const year = rawYear == null ? Number.NaN : Number(rawYear);
  if (
    venue == null ||
    rawYear == null ||
    !/^\d{4}$/.test(rawYear) ||
    !validVenueYear(venue, year)
  ) return null;
  return { venue, year };
}
