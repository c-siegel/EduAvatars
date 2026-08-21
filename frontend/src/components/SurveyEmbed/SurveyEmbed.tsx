import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import styles from "./SurveyEmbed.module.css";

interface SurveyEmbedProps {
  url: string;
  title: string;
  continueLabel: string;
  onContinue: () => void;
  onSkip: () => void;
}

// Reine <iframe src=…> Einbettung ohne zusätzliches embed.js von tally.so — minimiert die
// Drittanbieter-Anbindung (vgl. selbst gehostete Inter-Schrift, aus Datenschutzgründen).
export function SurveyEmbed({ url, title, continueLabel, onContinue, onSkip }: SurveyEmbedProps) {
  const { t } = useTranslation();
  const [loaded, setLoaded] = useState(false);

  return (
    <div className={styles.stage}>
      <p className={styles.notice}>{t("surveyEmbed.notice")}</p>

      <div className={styles.frameWrap}>
        {!loaded && <div className={styles.frameLoading}>{t("surveyEmbed.loading")}</div>}
        <iframe src={url} title={title} className={styles.iframe} loading="lazy" onLoad={() => setLoaded(true)} />
      </div>

      <div className={styles.actions}>
        <Button variant="accent" onClick={onContinue}>
          {continueLabel}
        </Button>
        <Button onClick={onSkip}>{t("surveyEmbed.skip")}</Button>
      </div>
    </div>
  );
}
