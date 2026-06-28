"use client";

/**
 * Half-circle gauge for an availability / reachability / demand-trust signal.
 * Value 0..1. Accessible via role=meter with aria-valuenow; the numeric label is
 * always shown so meaning is never color-only.
 */
export function Gauge({
  label,
  value,
  color = "#5BE0E6",
  size = 92,
}: {
  label: string;
  value: number;
  color?: string;
  size?: number;
}) {
  const v = Math.max(0, Math.min(1, value));
  const stroke = 9;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  // semicircle arc length
  const arc = Math.PI * r;
  const filled = arc * v;

  return (
    <div className="flex flex-col items-center">
      <svg
        width={size}
        height={size / 2 + 8}
        viewBox={`0 0 ${size} ${size / 2 + 8}`}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(v * 100)}
        aria-label={`${label}: ${Math.round(v * 100)} out of 100`}
      >
        <path
          d={`M ${stroke / 2} ${cy} A ${r} ${r} 0 0 1 ${size - stroke / 2} ${cy}`}
          fill="none"
          stroke="rgba(230,234,242,0.08)"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        <path
          d={`M ${stroke / 2} ${cy} A ${r} ${r} 0 0 1 ${size - stroke / 2} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${arc - filled}`}
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
      </svg>
      <div className="-mt-1 text-center">
        <div className="font-mono text-sm text-ink">{Math.round(v * 100)}</div>
        <div className="text-[11px] text-ink-mute">{label}</div>
      </div>
    </div>
  );
}
