import { getInitials } from "@/lib/initials";
import styles from "./Avatar.module.css";

interface AvatarProps {
  name: string;
  src?: string | null;
  size?: "sm" | "md" | "lg";
  selected?: boolean;
}

// Kreis mit Initialen (Fallback, solange keine echten Avatar-Bilder/3D-Renderings angebunden
// sind — 3D-Rendering ist bewusst nicht Teil dieser Struktur).
export function Avatar({ name, src, size = "md", selected }: AvatarProps) {
  const classes = [styles.avatar, styles[size], selected && styles.selected].filter(Boolean).join(" ");
  return (
    <span className={classes} aria-hidden="true">
      {src ? <img src={src} alt="" /> : getInitials(name)}
    </span>
  );
}
