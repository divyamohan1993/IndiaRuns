"use client";

import type { FitComponent } from "@/lib/derive";

/**
 * Segmented fit ring (SVG). Each arc is one fit component; arc length encodes
 * its value 0..1 across an equal angular slice, so the ring reads as a
 * decomposition. Accessible: role=img with a text summary; no color-only meaning
 * (each segment also labeled in the legend with its numeric value).
 */
export function FitRing({
  components,
  size = 120,
  stroke = 10,
  centerLabel,
}: {
  components: FitComponent[];
  size?: number;
  stroke?: number;
  centerLabel?: string;
}) {
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const n = components.length || 1;
  const segLen = circumference / n;
  const gap = Math.min(6, segLen * 0.08);

  const summary = components
    .map((c) => `${c.label} ${Math.round(c.value * 100)}%`)
    .join(", ");

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`Fit breakdown: ${summary}`}
      className="-rotate-90"
    >
      {/* track */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke="rgba(230,234,242,0.08)"
        strokeWidth={stroke}
      />
      {components.map((c, i) => {
        const filled = (segLen - gap) * c.value;
        const offset = -i * segLen;
        return (
          <circle
            key={c.key}
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={c.color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference - filled}`}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dasharray 0.6s ease" }}
          />
        );
      })}
      {centerLabel && (
        <text
          x={cx}
          y={cy}
          textAnchor="middle"
          dominantBaseline="central"
          className="rotate-90 fill-ink font-mono"
          style={{ transformOrigin: "center", fontSize: size * 0.18 }}
        >
          {centerLabel}
        </text>
      )}
    </svg>
  );
}
