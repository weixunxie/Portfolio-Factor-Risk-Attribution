export default function DisclaimerBanner() {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex items-start gap-3">
      <span className="text-amber-500 mt-0.5 text-lg leading-none select-none">
        &#9888;
      </span>
      <p className="text-sm text-amber-800">
        <strong>Disclaimer:</strong> This tool is for educational and research
        purposes only. It does not provide investment advice or trading
        recommendations.
      </p>
    </div>
  );
}
