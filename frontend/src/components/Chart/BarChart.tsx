import { useState } from "react";
import { formatCompactNumber } from "@/lib/format";
import styles from "./BarChart.module.css";

export interface BarChartDatum {
  label: string;
  value: number;
}

interface BarChartProps {
  data: BarChartDatum[];
  isFetching?: boolean;
}

// Rundet auf eine "glatte" Zahl auf (0/1.000/2.000 …), siehe dataviz-Skill "Y-axis ticks".
function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const residual = value / magnitude;
  const niceResidual = residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 5 ? 5 : 10;
  return niceResidual * magnitude;
}

// Balkendiagramm "Sessions im Zeitverlauf" (Screen 1f). Einzelne Serie -> keine Legende nötig
// (Titel der Karte benennt sie), teal-600 statt emerald-500 als Füllfarbe: emerald-500 liegt mit
// ~2.5:1 unter dem 3:1-Kontrast-Minimum für Marks auf hellem Grund, teal-600 schafft ~3.7:1.
export function BarChart({ data, isFetching }: BarChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (data.length === 0) {
    return <div className={styles.empty}>Keine Daten für diesen Zeitraum.</div>;
  }

  const max = niceMax(Math.max(...data.map((d) => d.value)));

  return (
    <div className={`${styles.chart} ${isFetching ? styles.fetching : ""}`}>
      <div className={styles.plotRow}>
        <div className={styles.yAxis}>
          <span>{formatCompactNumber(max)}</span>
          <span>{formatCompactNumber(max / 2)}</span>
          <span>0</span>
        </div>
        <div className={styles.plot}>
          <div className={styles.gridline} style={{ bottom: "0%" }} />
          <div className={styles.gridline} style={{ bottom: "50%" }} />
          <div className={styles.gridline} style={{ bottom: "100%" }} />
          <div className={styles.bars}>
            {data.map((point, index) => (
              <div
                key={`${point.label}-${index}`}
                className={styles.barSlot}
                tabIndex={0}
                role="img"
                aria-label={`${point.label}: ${point.value}`}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
                onFocus={() => setHoveredIndex(index)}
                onBlur={() => setHoveredIndex(null)}
              >
                <div className={styles.bar} style={{ height: `${(point.value / max) * 100}%` }} />
                {hoveredIndex === index && (
                  <div className={styles.tooltip}>
                    <strong>{point.value}</strong> · {point.label}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className={styles.xAxis}>
        <span>{data[0].label}</span>
        <span>{data[data.length - 1].label}</span>
      </div>
    </div>
  );
}
