export function projectPath(base: string, route: string): string {
  const normalizedBase = `/${base.split("/").filter(Boolean).join("/")}`;
  const normalizedRoute = route.split("/").filter(Boolean).join("/");
  return `${normalizedBase}/${normalizedRoute}${normalizedRoute ? "/" : ""}`;
}
