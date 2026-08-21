// API client for the public /settings/* backend routes: the unauthenticated view of the
// instance-wide site settings (contact email, whether self-registration is open).
import { apiClient } from "./client";

export interface PublicSiteSettings {
  contactEmail: string | null;
  registrationEnabled: boolean;
}

export const settingsApi = {
  getPublic: () => apiClient.get<PublicSiteSettings>("/settings/public"),
};
