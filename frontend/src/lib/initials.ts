// Shared by the sidebar user row (DashboardShell) and the project cards (Overview) —
// both show a circular badge with the first letters of a name/title.
export function getInitials(name?: string): string {
  if (!name) return "…";
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}
