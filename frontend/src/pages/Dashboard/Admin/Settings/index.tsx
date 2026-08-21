import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Input } from "@/components/Input";
import { adminApi, type SiteSettings } from "@/api/admin";
import { errorMessage } from "@/api/client";
import styles from "./AdminSettings.module.css";

const EMPTY_FORM: SiteSettings = {
  contactEmail: "",
  contactPhone: "",
  providerName: "",
  providerStreet: "",
  providerCity: "",
  providerCountry: "",
  registrationEnabled: true,
  conversationRetentionDays: 0,
};

/** Admin dashboard: instance-wide site settings (imprint details, registration, data retention). */
export function AdminSettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({ queryKey: ["admin", "settings"], queryFn: adminApi.getSettings });

  const [form, setForm] = useState<SiteSettings>(EMPTY_FORM);

  // Seeds the form from the loaded settings once, then only the user's own edits control it —
  // same pattern as the Configurator draft (see pages/Dashboard/Configurator).
  useEffect(() => {
    if (settingsQuery.data) {
      setForm({
        ...settingsQuery.data,
        // Null (never filled in) becomes "" so the inputs stay controlled.
        contactEmail: settingsQuery.data.contactEmail ?? "",
        contactPhone: settingsQuery.data.contactPhone ?? "",
        providerName: settingsQuery.data.providerName ?? "",
        providerStreet: settingsQuery.data.providerStreet ?? "",
        providerCity: settingsQuery.data.providerCity ?? "",
        providerCountry: settingsQuery.data.providerCountry ?? "",
      });
    }
  }, [settingsQuery.data]);

  function update(patch: Partial<SiteSettings>) {
    setForm((current) => ({ ...current, ...patch }));
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      adminApi.updateSettings({
        // Blank input means "not set" — send null so the public pages fall back to the
        // placeholder rather than rendering an empty line.
        contactEmail: form.contactEmail?.trim() || null,
        contactPhone: form.contactPhone?.trim() || null,
        providerName: form.providerName?.trim() || null,
        providerStreet: form.providerStreet?.trim() || null,
        providerCity: form.providerCity?.trim() || null,
        providerCountry: form.providerCountry?.trim() || null,
        registrationEnabled: form.registrationEnabled,
        conversationRetentionDays: form.conversationRetentionDays,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["admin", "settings"], updated);
      // The public /settings/public endpoint serves the same values — refetch so the Imprint and
      // privacy pages pick the change up without a reload.
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

      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.card}>
          <h3>{t("admin.settings.imprintTitle")}</h3>
          <p className={styles.hint}>{t("admin.settings.imprintHint")}</p>

          <Input
            label={t("admin.settings.providerNameLabel")}
            value={form.providerName ?? ""}
            onChange={(e) => update({ providerName: e.target.value })}
          />
          <Input
            label={t("admin.settings.providerStreetLabel")}
            value={form.providerStreet ?? ""}
            onChange={(e) => update({ providerStreet: e.target.value })}
          />
          <Input
            label={t("admin.settings.providerCityLabel")}
            value={form.providerCity ?? ""}
            onChange={(e) => update({ providerCity: e.target.value })}
          />
          <Input
            label={t("admin.settings.providerCountryLabel")}
            value={form.providerCountry ?? ""}
            onChange={(e) => update({ providerCountry: e.target.value })}
          />
          <Input
            label={t("admin.settings.contactEmailLabel")}
            type="email"
            placeholder="kontakt@example.com"
            value={form.contactEmail ?? ""}
            onChange={(e) => update({ contactEmail: e.target.value })}
          />
          <Input
            label={t("admin.settings.contactPhoneLabel")}
            value={form.contactPhone ?? ""}
            onChange={(e) => update({ contactPhone: e.target.value })}
          />
        </div>

        <div className={styles.card}>
          <h3>{t("admin.settings.privacyTitle")}</h3>

          <Input
            label={t("admin.settings.retentionLabel")}
            type="number"
            min={0}
            value={String(form.conversationRetentionDays)}
            onChange={(e) => update({ conversationRetentionDays: Math.max(0, Number(e.target.value) || 0) })}
          />
          <p className={styles.hint}>{t("admin.settings.retentionHint")}</p>

          <label className={styles.toggleRow}>
            <input
              type="checkbox"
              checked={form.registrationEnabled}
              onChange={(e) => update({ registrationEnabled: e.target.checked })}
            />
            <span className={styles.toggleCopy}>
              <strong>{t("admin.settings.registrationTitle")}</strong>
              <span>{t("admin.settings.registrationText")}</span>
            </span>
          </label>
        </div>

        {saveMutation.isError && (
          <Callout variant="danger">{errorMessage(saveMutation.error, t("admin.settings.saveError"))}</Callout>
        )}
        {saveMutation.isSuccess && <Callout variant="success">{t("admin.settings.saved")}</Callout>}

        <div>
          <Button type="submit" variant="accent" disabled={saveMutation.isPending}>
            {t("admin.settings.save")}
          </Button>
        </div>
      </form>
    </div>
  );
}
