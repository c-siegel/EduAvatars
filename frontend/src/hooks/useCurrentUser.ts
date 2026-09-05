import { useQuery } from "@tanstack/react-query";
import { authApi } from "@/api/auth";

// Backs both the sidebar user row (1c) and the dashboard auth guard: a failed
// fetch here (401) is how DashboardShell knows to redirect to /login.
export function useCurrentUser() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    retry: false,
  });
}
