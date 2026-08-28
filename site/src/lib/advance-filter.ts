import { projectPath } from "./paths";

export interface AdvanceFilter {
  venue: string;
  year: number;
  track: string;
}

function validScope(venue: string, year: number, track: string): boolean {
  return /^[A-Z0-9-]+$/.test(venue) && Number.isInteger(year) && year >= 1900 && year <= 3000
    && /^[a-z0-9-]+$/.test(track);
}

export function advanceFilterHref(base: string, venue: string, year: number, track: string): string {
  if (!validScope(venue, year, track)) throw new Error("Invalid advance filter");
  const query = new URLSearchParams({ venue, year: String(year), track });
  return `${projectPath(base, "advances")}?${query.toString()}#advance-${venue}-${year}-${track}`;
}

export function parseAdvanceFilter(search: string): AdvanceFilter | null {
  const query = new URLSearchParams(search);
  const venue = query.get("venue");
  const rawYear = query.get("year");
  const track = query.get("track");
  const year = rawYear == null ? Number.NaN : Number(rawYear);
  if (
    venue == null ||
    rawYear == null ||
    track == null ||
    !/^\d{4}$/.test(rawYear) ||
    !validScope(venue, year, track)
  ) return null;
  return { venue, year, track };
}
