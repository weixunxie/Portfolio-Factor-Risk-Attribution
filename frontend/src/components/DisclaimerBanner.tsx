export default function DisclaimerBanner() {
  return (
    <div
      style={{
        borderTop: "1px solid var(--border-lt)",
        paddingTop: 16,
        marginTop: 40,
      }}
    >
      <p style={{ color: "var(--faint)", fontSize: 11, lineHeight: 1.6 }}>
        For educational and research purposes only. This tool does not constitute investment advice,
        a solicitation, or a recommendation to buy, sell, or hold any security. All analysis is
        based on historical data. Past performance is not indicative of future results.
      </p>
    </div>
  );
}
