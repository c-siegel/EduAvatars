import { useEffect } from "react";
import { RotateCcw } from "lucide-react";
import { Input, Textarea } from "@/components/Input";
import { Button } from "@/components/Button";
import { DEFAULT_PREPROMPT } from "@/lib/preprompt";
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
  useEffect(() => {
    if (autoGenerate) {
      onChange({ preprompt: DEFAULT_PREPROMPT });
      onGenerated();
    }
    // Nur beim ersten Betreten von Schritt 3 automatisch befüllen, solange preprompt leer ist.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoGenerate]);

  function resetToDefault() {
    onChange({ preprompt: DEFAULT_PREPROMPT });
  }

  return (
    <div>
      <Input
        label="Zielgruppe / Klassenstufe"
        placeholder="z. B. Klasse 7b"
        value={draft.gradeLevel}
        onChange={(e) => onChange({ gradeLevel: e.target.value })}
      />

      <div className={styles.toolbar}>
        <Button size="sm" onClick={resetToDefault}>
          <RotateCcw size={14} /> Auf Standard zurücksetzen
        </Button>
      </div>
      <Textarea
        label="Preprompt / Rolle"
        hint={`${draft.preprompt.length} / ${MAX_LENGTH}`}
        value={draft.preprompt}
        onChange={(e) => onChange({ preprompt: e.target.value.slice(0, MAX_LENGTH) })}
        rows={12}
      />
      <p className={styles.hint}>"Auf Standard zurücksetzen" ersetzt den aktuellen Text durch den generischen Standardtext.</p>

      <Textarea
        label="Startnachricht (optional)"
        hint={`${draft.startPrompt.length} / ${START_PROMPT_MAX_LENGTH}`}
        value={draft.startPrompt}
        onChange={(e) => onChange({ startPrompt: e.target.value.slice(0, START_PROMPT_MAX_LENGTH) })}
        rows={4}
      />
      <p className={styles.hint}>
        Wird Schüler:innen als erste Nachricht des Avatars gezeigt — anders als der Preprompt oben
        kennt das Modell diesen Text ebenfalls (z. B. für eine Aufgabenstellung, auf die geantwortet
        werden soll). Leer lassen für eine generische Begrüßung.
      </p>
    </div>
  );
}
