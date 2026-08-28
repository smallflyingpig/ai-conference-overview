import { projectPath } from "./paths";

export interface PaperScopeFilter {
  venue: string;
  year: number;
  track: string;
}

export function paperFilterHref(
  base: string,
  venue: string,
  year: number,
  track: string,
): string {
  if (!/^[A-Z0-9-]+$/.test(venue) || !Number.isInteger(year) || !/^[a-z0-9-]+$/.test(track)) {
    throw new Error("Invalid paper filter");
  }
  const query = new URLSearchParams({ venue, year: String(year), track });
  return `${projectPath(base, "papers")}?${query.toString()}`;
}

export function parsePaperScopeFilter(search: string): PaperScopeFilter | null {
  const query = new URLSearchParams(search);
  const venue = query.get("venue");
  const rawYear = query.get("year");
  const track = query.get("track");
  const year = rawYear == null ? Number.NaN : Number(rawYear);
  if (
    venue == null ||
    rawYear == null ||
    track == null ||
    !/^[A-Z0-9-]+$/.test(venue) ||
    !/^\d{4}$/.test(rawYear) ||
    !Number.isInteger(year) ||
    year < 1900 ||
    year > 3000 ||
    !/^[a-z0-9-]+$/.test(track)
  ) return null;
  return { venue, year, track };
}
