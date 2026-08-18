import { useState } from "react";
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
  const [loaded, setLoaded] = useState(false);

  return (
    <div className={styles.stage}>
      <p className={styles.notice}>
        Diese Umfrage wird von einem externen Anbieter (Tally) bereitgestellt. Beim Laden wird eine
        Verbindung zu tally.so hergestellt.
      </p>

      <div className={styles.frameWrap}>
        {!loaded && <div className={styles.frameLoading}>Umfrage wird geladen …</div>}
        <iframe src={url} title={title} className={styles.iframe} loading="lazy" onLoad={() => setLoaded(true)} />
      </div>

      <div className={styles.actions}>
        <Button variant="accent" onClick={onContinue}>
          {continueLabel}
        </Button>
        <Button onClick={onSkip}>Überspringen</Button>
      </div>
    </div>
  );
}
