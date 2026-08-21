export interface User {
  id: string;
  name: string;
  school: string | null;
  email: string;
  avatarUrl: string | null;
  isAdmin: boolean;
  // Whether this account must change its password before reaching the rest of the dashboard —
  // set when an admin creates the account or resets its password (see layouts/DashboardShell.tsx).
  mustChangePassword: boolean;
}
