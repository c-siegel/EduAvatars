import i18n from "@/i18n";

// Relative-time label for "Zuletzt: …" on project cards (Screen 1d). Uses i18next's plural
// forms (time.daysAgo_one/_other etc. in the locale files) instead of hand-rolled English/German
// pluralization — German's "Monat"/"Monaten" split needs it just as much as English does.
export function formatRelativeDate(iso: string): string {
  const diffDays = Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) return i18n.t("time.today");
  if (diffDays === 1) return i18n.t("time.yesterday");
  if (diffDays < 7) return i18n.t("time.daysAgo", { count: diffDays });

  const weeks = Math.floor(diffDays / 7);
  if (weeks < 5) return i18n.t("time.weeksAgo", { count: weeks });

  const months = Math.floor(diffDays / 30);
  return i18n.t("time.monthsAgo", { count: months });
}
