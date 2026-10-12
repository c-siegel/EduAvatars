// Queries shared by the cards of the pronunciation page.

import { useQuery } from "@tanstack/react-query";
import { pronunciationApi } from "@/api/pronunciation";
import type { SpokenLanguage } from "@/types/project";

// Every pronunciation query starts with this, so one invalidation refreshes the list, the
// presets' "applied" counts and anything else derived from the entries.
export const PRONUNCIATION_QUERY_KEY = ["pronunciation"];

/** The teacher's entries for one language, alphabetically. */
export function useEntries(language: SpokenLanguage) {
  return useQuery({
    queryKey: [...PRONUNCIATION_QUERY_KEY, "entries", language],
    queryFn: () => pronunciationApi.list(language),
  });
}
