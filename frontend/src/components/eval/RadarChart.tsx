interface RadarChartProps {
  scores: {
    context_precision: number | null;
    context_recall: number | null;
    answer_faithfulness: number | null;
    answer_relevance: number | null;
  };
}

const SIZE = 200;
const CENTER = SIZE / 2;
const RADIUS = 75;
const LABELS = [
  { key: "context_precision", label: "Precision", angle: -90 },
  { key: "answer_relevance", label: "Relevance", angle: 0 },
  { key: "context_recall", label: "Recall", angle: 90 },
  { key: "answer_faithfulness", label: "Faithful", angle: 180 },
] as const;

function polar(angle: number, r: number): [number, number] {
  const rad = (angle * Math.PI) / 180;
  return [CENTER + r * Math.cos(rad), CENTER + r * Math.sin(rad)];
}

export function RadarChart({ scores }: RadarChartProps) {
  const points = LABELS.map(({ key, angle }) => {
    const val = scores[key] ?? 0;
    return polar(angle, val * RADIUS);
  });

  const polygon = points.map(([x, y]) => `${x},${y}`).join(" ");
  const gridPolygon = LABELS.map(({ angle }) => polar(angle, RADIUS))
    .map(([x, y]) => `${x},${y}`)
    .join(" ");
  const halfPolygon = LABELS.map(({ angle }) => polar(angle, RADIUS * 0.5))
    .map(([x, y]) => `${x},${y}`)
    .join(" ");

  return (
    <div className="flex flex-col items-center gap-2">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-48 h-48">
        {/* Grid rings */}
        <polygon points={gridPolygon} fill="none" stroke="currentColor" strokeOpacity={0.15} />
        <polygon points={halfPolygon} fill="none" stroke="currentColor" strokeOpacity={0.1} />
        {/* Axis lines */}
        {LABELS.map(({ key, angle }) => {
          const [x, y] = polar(angle, RADIUS);
          return <line key={key} x1={CENTER} y1={CENTER} x2={x} y2={y} stroke="currentColor" strokeOpacity={0.15} />;
        })}
        {/* Score polygon */}
        <polygon
          points={polygon}
          fill="hsl(var(--primary))"
          fillOpacity={0.25}
          stroke="hsl(var(--primary))"
          strokeWidth={1.5}
        />
        {/* Labels */}
        {LABELS.map(({ key, label, angle }) => {
          const [x, y] = polar(angle, RADIUS + 18);
          return (
            <text
              key={key}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize={10}
              fill="currentColor"
              opacity={0.7}
            >
              {label}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
