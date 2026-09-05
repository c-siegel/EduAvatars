import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Outlet, useNavigate } from "react-router-dom";
import { LandingPage } from "./pages/Landing";
import { LoginPage } from "./pages/Login";
import { RegisterPage } from "./pages/Register";
import { ForgotPasswordPage } from "./pages/ForgotPassword";
import { ResetPasswordPage } from "./pages/ResetPassword";
import { OverviewPage } from "./pages/Dashboard/Overview";
import { ConfiguratorPage } from "./pages/Dashboard/Configurator";
import { AnalyticsPage } from "./pages/Dashboard/Analytics";
import { ApiDashboardPage } from "./pages/Dashboard/ApiDashboard";
import { ProfilePage } from "./pages/Dashboard/Profile";
import { AdminUsersPage } from "./pages/Dashboard/Admin/Users";
import { AdminSettingsPage } from "./pages/Dashboard/Admin/Settings";
import { ForcePasswordChangePage } from "./pages/Dashboard/ForcePasswordChange";
import { PublicChatPage } from "./pages/PublicChat";
import { ImprintPage } from "./pages/Imprint";
import { PrivacyPage } from "./pages/Privacy";
import { CreditsPage } from "./pages/Credits";
import { DashboardShell } from "./layouts/DashboardShell";
import { RequireAdmin } from "./components/RequireAdmin";
import { setNavigate } from "./lib/navigation";

// Layout route: wraps every /dashboard/* screen in the shared sidebar shell (Screen 1c).
function DashboardLayout() {
  return (
    <DashboardShell>
      <Outlet />
    </DashboardShell>
  );
}

/** Hands this router's navigate() to lib/navigation.ts so code outside the component tree (the
 * global QueryClient error handler in main.tsx) can redirect on a session-expired response.
 * Renders nothing — must live inside <BrowserRouter> for useNavigate() to work. */
function NavigateBridge() {
  const navigate = useNavigate();
  useEffect(() => {
    setNavigate(navigate);
  }, [navigate]);
  return null;
}

export function App() {
  return (
    <BrowserRouter>
      <NavigateBridge />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/impressum" element={<ImprintPage />} />
        <Route path="/datenschutz" element={<PrivacyPage />} />
        <Route path="/credits" element={<CreditsPage />} />
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<OverviewPage />} />
          <Route path="projects/:id" element={<ConfiguratorPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="api" element={<ApiDashboardPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="change-password-required" element={<ForcePasswordChangePage />} />
          <Route path="admin" element={<RequireAdmin> <AdminUsersPage /> </RequireAdmin> } />
          <Route path="admin/settings" element={<RequireAdmin> <AdminSettingsPage /> </RequireAdmin> } />
        </Route>
        <Route path="/c/:projectSlug" element={<PublicChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}