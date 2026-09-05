import React from "react";
import ReactDOM from "react-dom/client";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { ApiError, isSessionExpiredError } from "./api/client";
import { navigateTo } from "./lib/navigation";
import "./i18n";
import "./styles/globals.css";

// DashboardShell's own 401 guard only reacts to the initial `["auth","me"]` query — an auth
// cookie that expires mid-edit (e.g. in the Configurator) otherwise just shows a generic "could
// not save" error forever, with no path back to the login page. This catches it centrally, for
// every query and mutation in the app, instead of every call site needing its own onError.
function handleQueryError(error: unknown): void {
  if (isSessionExpiredError(error)) {
    queryClient.removeQueries({ queryKey: ["auth", "me"] });
    navigateTo("/login", { replace: true });
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 4xx (bad request, not found, an expired session, ...) isn't going to change on retry —
      // only worth retrying transient/server errors. Without this, a query (unlike a mutation,
      // which already defaults to no retries) hitting a session-expired 401 would retry 3 times
      // over several seconds before handleQueryError below ever gets to redirect.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failureCount < 3,
    },
  },
  queryCache: new QueryCache({ onError: handleQueryError }),
  mutationCache: new MutationCache({ onError: handleQueryError }),
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
