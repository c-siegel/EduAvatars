import { Link } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import styles from "./NavItem.module.css";

interface NavItemProps {
  to: string;
  icon: LucideIcon;
  active?: boolean;
  onClick?: () => void;
  children: string;
}

export function NavItem({ to, icon: Icon, active, onClick, children }: NavItemProps) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className={[styles.navItem, active && styles.active].filter(Boolean).join(" ")}
      aria-current={active ? "page" : undefined}
    >
      <Icon size={18} strokeWidth={2} />
      {children}
    </Link>
  );
}
