import type { ReactNode } from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import styles from "./Callout.module.css";

export type CalloutVariant = "danger" | "warning" | "info" | "success";

const ICONS: Record<CalloutVariant, typeof AlertCircle> = {
  danger: AlertCircle,
  warning: AlertTriangle,
  info: Info,
  success: CheckCircle2,
};

interface CalloutProps {
  variant?: CalloutVariant;
  children: ReactNode;
}

export function Callout({ variant = "info", children }: CalloutProps) {
  const Icon = ICONS[variant];
  return (
    <div className={[styles.callout, styles[variant]].join(" ")} role={variant === "danger" ? "alert" : "status"}>
      <Icon size={18} strokeWidth={2} aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}
