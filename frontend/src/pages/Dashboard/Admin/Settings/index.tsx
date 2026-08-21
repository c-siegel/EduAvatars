import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Input } from "@/components/Input";
import { adminApi } from "@/api/admin";
import { errorMessage } from "@/api/client";
import styles from "./AdminSettings.module.css";

/** Admin dashboard: instance-wide site settings (contact email, self-registration toggle). */
export function AdminSettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({ queryKey: ["admin", "settings"], queryFn: adminApi.getSettings });

  const [contactEmail, setContactEmail] = useState("");
  const [registrationEnabled, setRegistrationEnabled] = useState(true);

  // Seeds the form from the loaded settings once, then only the user's own edits control it —
  // same pattern as the Configurator draft (see pages/Dashboard/Configurator).
  useEffect(() => {
    if (settingsQuery.data) {
      setContactEmail(settingsQuery.data.contactEmail ?? "");
      setRegistrationEnabled(settingsQuery.data.registrationEnabled);
    }
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      adminApi.updateSettings({ contactEmail: contactEmail.trim() || null, registrationEnabled }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["admin", "settings"], updated);
      // The public /settings/public endpoint returns the same data — refetch so the Imprint page
      // (and anyone else reading it) picks up the change without a reload.
      queryClient.invalidateQueries({ queryKey: ["settings", "public"] });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (saveMutation.isPending) return;
    saveMutation.mutate();
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h2>{t("admin.settings.title")}</h2>
        <p>{t("admin.settings.subtitle")}</p>
      </div>

      <form className={styles.card} onSubmit={handleSubmit}>
        <Input
          label={t("admin.settings.contactEmailLabel")}
          type="email"
          placeholder="kontakt@example.com"
          value={contactEmail}
          onChange={(e) => setContactEmail(e.target.value)}
        />
        <p className={styles.hint}>{t("admin.settings.contactEmailHint")}</p>

        <label className={styles.toggleRow}>
          <input
            type="checkbox"
            checked={registrationEnabled}
            onChange={(e) => setRegistrationEnabled(e.target.checked)}
          />
          <span className={styles.toggleCopy}>
            <strong>{t("admin.settings.registrationTitle")}</strong>
            <span>{t("admin.settings.registrationText")}</span>
          </span>
        </label>

        {saveMutation.isError && (
          <Callout variant="danger">{errorMessage(saveMutation.error, t("admin.settings.saveError"))}</Callout>
        )}
        {saveMutation.isSuccess && <Callout variant="success">{t("admin.settings.saved")}</Callout>}

        <Button type="submit" variant="accent" disabled={saveMutation.isPending}>
          {t("admin.settings.save")}
        </Button>
      </form>
    </div>
  );
}
