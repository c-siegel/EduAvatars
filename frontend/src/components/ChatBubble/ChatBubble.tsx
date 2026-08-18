import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "./ChatBubble.module.css";

interface ChatBubbleProps {
  role: "user" | "assistant";
  content: string;
}

export function ChatBubble({ role, content }: ChatBubbleProps) {
  return (
    <div className={[styles.row, role === "user" && styles.me].filter(Boolean).join(" ")}>
      <div className={styles.bubble}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}

// Tippindikator während auf die Bot-Antwort gewartet wird (Live-Vorschau 1e, Chat 1i)
export function TypingBubble() {
  return (
    <div className={styles.row}>
      <div className={styles.bubble}>
        <span className={styles.typing} aria-label="Antwort wird geschrieben …">
          <span />
          <span />
          <span />
        </span>
      </div>
    </div>
  );
}
