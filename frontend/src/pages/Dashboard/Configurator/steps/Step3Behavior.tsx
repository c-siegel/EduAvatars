import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { RotateCcw } from "lucide-react";
import { Input, Textarea } from "@/components/Input";
import { Button } from "@/components/Button";
import type { StepProps } from "../types";
import styles from "./Step3Behavior.module.css";

const MAX_LENGTH = 2000;
const START_PROMPT_MAX_LENGTH = 1000;

interface Step3Props extends StepProps {
  autoGenerate: boolean;
  onGenerated: () => void;
}

// Schritt 3 — Verhalten: Zielgruppe, Preprompt (mit generischem Standardtext) und Startnachricht.
export function Step3Behavior({ draft, onChange, autoGenerate, onGenerated }: Step3Props) {
  const { t } = useTranslation();
  const defaultPreprompt = t("configurator.step3.defaultPreprompt");

  useEffect(() => {
    if (autoGenerate) {
      onChange({ preprompt: defaultPreprompt });
      onGenerated();
    }
    // Nur beim ersten Betreten von Schritt 3 automatisch befüllen, solange preprompt leer ist.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoGenerate]);

  function resetToDefault() {
    onChange({ preprompt: defaultPreprompt });
  }

  return (
    <div>
      <Input
        label={t("configurator.step3.targetGroup")}
        placeholder={t("configurator.step3.targetGroupPlaceholder")}
        value={draft.gradeLevel}
        onChange={(e) => onChange({ gradeLevel: e.target.value })}
      />

      <div className={styles.toolbar}>
        <Button size="sm" onClick={resetToDefault}>
          <RotateCcw size={14} /> {t("configurator.step3.resetToDefault")}
        </Button>
      </div>
      <Textarea
        label={t("configurator.step3.preprompt")}
        hint={`${draft.preprompt.length} / ${MAX_LENGTH}`}
        value={draft.preprompt}
        onChange={(e) => onChange({ preprompt: e.target.value.slice(0, MAX_LENGTH) })}
        rows={12}
      />
      <p className={styles.hint}>{t("configurator.step3.resetHint")}</p>

      <Textarea
        label={t("configurator.step3.startMessageOptional")}
        hint={`${draft.startPrompt.length} / ${START_PROMPT_MAX_LENGTH}`}
        value={draft.startPrompt}
        onChange={(e) => onChange({ startPrompt: e.target.value.slice(0, START_PROMPT_MAX_LENGTH) })}
        rows={4}
      />
      <p className={styles.hint}>{t("configurator.step3.startMessageHint")}</p>
    </div>
  );
}
