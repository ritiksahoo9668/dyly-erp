import type { Tone } from "./onboardingFormat";
import styles from "./UserOnboardingPage.module.css";

export function Badge({ label, tone, dot = false }: { label: string; tone: Tone; dot?: boolean }) {
  return (
    <span className={`${styles.badge} ${styles[`tone_${tone}`]}`}>
      {dot ? <i aria-hidden="true" /> : null}
      {label}
    </span>
  );
}
