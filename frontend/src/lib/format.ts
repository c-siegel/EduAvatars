import i18n from "@/i18n";

// The digit-grouping/date-formatting locale follows the UI language; a currency amount's
// currency itself (EUR) doesn't. Shared by every Intl.NumberFormat/DateTimeFormat call site.
export function numberLocale(): string {
  return i18n.language === "en" ? "en-US" : "de-DE";
}

export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat(numberLocale(), { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function formatEuro(value: number): string {
  return new Intl.NumberFormat(numberLocale(), { style: "currency", currency: "EUR" }).format(value);
}

export function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.round(totalSeconds % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/** "1,4 MB" / "820 KB" — file sizes in the knowledge-base pages. */
export function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toLocaleString(numberLocale(), { maximumFractionDigits: unit === 0 ? 0 : 1 })} ${units[unit]}`;
}
