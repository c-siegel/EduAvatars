import type { HTMLAttributes } from "react";
import styles from "./Badge.module.css";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "accent" | "danger";
}

const VARIANT_CLASS = {
  default: undefined,
  accent: styles.accent,
  danger: styles.danger,
} as const;

export function Badge({ variant = "default", className, ...props }: BadgeProps) {
  const classes = [styles.badge, VARIANT_CLASS[variant], className].filter(Boolean).join(" ");
  return <span className={classes} {...props} />;
}
