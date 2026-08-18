import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
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
import { PublicChatPage } from "./pages/PublicChat";
import { ImprintPage } from "./pages/Imprint";
import { CreditsPage } from "./pages/Credits";
import { DashboardShell } from "./layouts/DashboardShell";

// Layout route: wraps every /dashboard/* screen in the shared sidebar shell (Screen 1c).
function DashboardLayout() {
  return (
    <DashboardShell>
      <Outlet />
    </DashboardShell>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/impressum" element={<ImprintPage />} />
        <Route path="/credits" element={<CreditsPage />} />
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<OverviewPage />} />
          <Route path="projects/:id" element={<ConfiguratorPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="api" element={<ApiDashboardPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
        <Route path="/c/:projectSlug" element={<PublicChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}