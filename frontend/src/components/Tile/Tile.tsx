import type { ReactNode } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import styles from "./Tile.module.css";

interface TileDelta {
  value: number;
  /** Direction that counts as positive — e.g. "down" for costs/error rates. Default "up". */
  goodDirection?: "up" | "down";
}

interface TileProps {
  label: string;
  value: ReactNode;
  delta?: TileDelta;
  children?: ReactNode;
}

// Stat tile, e.g. "Projects" -> 6 (screen 1d) or with a trend delta (screen 1f).
// The delta carries a sign + icon in addition to colour (never colour alone), see the dataviz skill.
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
