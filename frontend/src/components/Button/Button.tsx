import type { ButtonHTMLAttributes } from "react";
import { Link, type LinkProps } from "react-router-dom";
import styles from "./Button.module.css";

export type ButtonVariant = "default" | "filled" | "accent" | "danger";
export type ButtonSize = "md" | "sm";

function classNames(variant: ButtonVariant, size: ButtonSize, fullWidth?: boolean) {
  return [
    styles.btn,
    variant === "filled" && styles.filled,
    variant === "accent" && styles.accent,
    variant === "danger" && styles.danger,
    size === "sm" && styles.sm,
    fullWidth && styles.fullWidth,
  ]
    .filter(Boolean)
    .join(" ");
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
}

export function Button({ variant = "default", size = "md", fullWidth, className, ...props }: ButtonProps) {
  return <button className={[classNames(variant, size, fullWidth), className].filter(Boolean).join(" ")} {...props} />;
}

interface ButtonLinkProps extends LinkProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
}

export function ButtonLink({ variant = "default", size = "md", fullWidth, className, ...props }: ButtonLinkProps) {
  return <Link className={[classNames(variant, size, fullWidth), className].filter(Boolean).join(" ")} {...props} />;
}
