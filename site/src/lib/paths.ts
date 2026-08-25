export function projectPath(base: string, route: string): string {
  const baseSegments = base.split("/").filter(Boolean);
  const normalizedBase = baseSegments.length === 0
    ? "/ai-conference-overview"
    : `/${baseSegments.join("/")}`;
  const normalizedRoute = route.split("/").filter(Boolean).join("/");
  return `${normalizedBase}/${normalizedRoute}${normalizedRoute ? "/" : ""}`;
}

export function conferenceNavigationHref(
  base: string,
  conferenceAvailable: boolean,
): string | null {
  return conferenceAvailable ? projectPath(base, "conferences/acl/2026") : null;
}
