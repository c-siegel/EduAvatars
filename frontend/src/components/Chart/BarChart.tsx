import { useState } from "react";
import { useTranslation } from "react-i18next";
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

// Rounds up to a "nice" number (0/1,000/2,000 …), see the dataviz skill "Y-axis ticks".
function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const residual = value / magnitude;
  const niceResidual = residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 5 ? 5 : 10;
  return niceResidual * magnitude;
}

// Bar chart "Sessions over time" (screen 1f). Single series -> no legend needed (the card title
// names it). teal-600 instead of emerald-500 as fill colour: at ~2.5:1 emerald-500 falls below the
// 3:1 contrast minimum for marks on a light background, teal-600 reaches ~3.7:1.
export function BarChart({ data, isFetching }: BarChartProps) {
  const { t } = useTranslation();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (data.length === 0) {
    return <div className={styles.empty}>{t("analytics.chartEmpty")}</div>;
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
