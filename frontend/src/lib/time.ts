// Simple German relative-time formatting for "Zuletzt: …" on project cards (Screen 1d).
export function formatRelativeDate(iso: string): string {
  const diffDays = Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) return "heute";
  if (diffDays === 1) return "gestern";
  if (diffDays < 7) return `vor ${diffDays} Tagen`;

  const weeks = Math.floor(diffDays / 7);
  if (weeks === 1) return "vor 1 Woche";
  if (weeks < 5) return `vor ${weeks} Wochen`;

  const months = Math.floor(diffDays / 30);
  return `vor ${months} Monat${months === 1 ? "" : "en"}`;
}
