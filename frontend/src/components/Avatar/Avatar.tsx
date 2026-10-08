import { getInitials } from "@/lib/initials";
import styles from "./Avatar.module.css";

interface AvatarProps {
  name: string;
  src?: string | null;
  size?: "sm" | "md" | "lg";
  selected?: boolean;
}

// Circle with initials (fallback as long as no real avatar images/3D renderings are wired up —
// 3D rendering is deliberately not part of this structure).
export function Avatar({ name, src, size = "md", selected }: AvatarProps) {
  const classes = [styles.avatar, styles[size], selected && styles.selected].filter(Boolean).join(" ");
  return (
    <span className={classes} aria-hidden="true">
      {src ? <img src={src} alt="" /> : getInitials(name)}
    </span>
  );
}
