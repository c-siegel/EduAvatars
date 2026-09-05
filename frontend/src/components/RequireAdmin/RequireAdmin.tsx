import { useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useCurrentUser } from "@/hooks/useCurrentUser";

/** Redirects to /dashboard unless the current user is an admin; renders nothing while deciding. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  // The 401 (not logged in at all) case is already handled by DashboardShell's own guard, since
  // every admin route is nested inside it — this only needs to gate on the admin flag.
  const { data: user, isLoading } = useCurrentUser();

  useEffect(() => {
    if (!isLoading && user && !user.isAdmin) {
      navigate("/dashboard", { replace: true });
    }
  }, [isLoading, user, navigate]);

  if (!user?.isAdmin) return null;
  return <>{children}</>;
}
