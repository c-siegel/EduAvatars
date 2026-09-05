import type { ReactNode } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import styles from "./Tile.module.css";

interface TileDelta {
  value: number;
  /** Richtung, die als positiv gilt — z.B. "down" für Kosten/Fehlerraten. Default "up". */
  goodDirection?: "up" | "down";
}

interface TileProps {
  label: string;
  value: ReactNode;
  delta?: TileDelta;
  children?: ReactNode;
}

// Statistik-Kachel, z.B. "Projekte" -> 6 (Screen 1d) oder mit Trend-Delta (Screen 1f).
// Delta trägt Vorzeichen + Icon zusätzlich zur Farbe (nie Farbe allein), siehe dataviz-Skill.
export function Tile({ label, value, delta, children }: TileProps) {
  const isGood = delta ? (delta.goodDirection === "down" ? delta.value <= 0 : delta.value >= 0) : null;
  const DeltaIcon = delta && delta.value >= 0 ? TrendingUp : TrendingDown;

  return (
    <div className={styles.tile}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
      {delta && (
        <span className={`${styles.delta} ${isGood ? styles.deltaGood : styles.deltaBad}`}>
          <DeltaIcon size={14} strokeWidth={2} />
          {delta.value > 0 ? "+" : ""}
          {delta.value}%
        </span>
      )}
      {children}
    </div>
  );
}
