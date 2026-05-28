export type MetricColor = "positive" | "negative" | "warning" | "neutral";

interface Props {
  label: string;
  value: string;
  helper?: string;
  color?: MetricColor;
}

const VALUE_COLOR: Record<MetricColor, string> = {
  positive: "var(--positive)",
  negative: "var(--negative)",
  warning:  "var(--warning)",
  neutral:  "var(--text)",
};

export default function MetricCard({ label, value, helper, color = "neutral" }: Props) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        padding: "12px 14px",
      }}
    >
      <p
        style={{
          color: "var(--faint)",
          fontSize: 9.5,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.09em",
          marginBottom: 6,
        }}
      >
        {label}
      </p>
      <p
        style={{
          color: VALUE_COLOR[color],
          fontSize: 20,
          fontWeight: 600,
          lineHeight: 1,
          marginBottom: helper ? 5 : 0,
          letterSpacing: "-0.01em",
        }}
      >
        {value}
      </p>
      {helper && (
        <p style={{ color: "var(--faint)", fontSize: 10.5, lineHeight: 1.4 }}>
          {helper}
        </p>
      )}
    </div>
  );
}
