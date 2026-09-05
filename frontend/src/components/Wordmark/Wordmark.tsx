import styles from "./Wordmark.module.css";

export function Wordmark() {
  return (
    <span className={styles.wordmark}>
      Edu
      {/* "Avatars" carries the brand gradient (emerald → teal), see .accent below */}
      <span className={styles.accent}>Avatars</span>
    </span>
  );
}
