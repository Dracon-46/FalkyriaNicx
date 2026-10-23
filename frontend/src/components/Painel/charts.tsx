import { useId, useState, type ReactNode } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts';
import { Inbox, Table2, BarChart3 } from 'lucide-react';
import { fmtCompact, fmtDayLong, fmtDayShort, fmtInt, fmtPercent } from './format';

/*
 * Chart pieces for the painel, following the dataviz method: thin marks,
 * hairline solid grid, 2px lines, 4px rounded data ends square at the
 * baseline, a 2px surface gap between stacked segments, one hover tooltip
 * per position (value first, series second, line keys) and a table view
 * twin for every chart. Colors come from the --viz-* roles in painel.css.
 */

const TICK = { fill: 'var(--viz-tick)', fontSize: 11 };
const AXIS_LINE = { stroke: 'var(--viz-axis)' };

// ---------------------------------------------------------------------------
// Card + empty state + table toggle
// ---------------------------------------------------------------------------

export function EmptyState({ children, compact = false }: { children: ReactNode; compact?: boolean }) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 text-center px-6 ${compact ? 'py-6' : 'py-10'}`}
      style={{ color: 'var(--color-text-secondary)' }}
    >
      <Inbox size={18} aria-hidden="true" style={{ color: 'var(--color-text-tertiary)' }} />
      <p className="text-xs max-w-xs leading-relaxed">{children}</p>
    </div>
  );
}

interface ChartCardProps {
  title: string;
  subtitle?: string;
  /** Accessible twin of the chart; a toggle appears when given. */
  table?: ReactNode;
  legend?: ReactNode;
  empty?: boolean;
  emptyText?: string;
  children: ReactNode;
  className?: string;
}

export function ChartCard({
  title,
  subtitle,
  table,
  legend,
  empty = false,
  emptyText = 'Sem dados neste período.',
  children,
  className = '',
}: ChartCardProps) {
  const [showTable, setShowTable] = useState(false);
  const titleId = useId();
  return (
    <figure className={`hud-panel p-4 flex flex-col min-w-0 ${className}`} aria-labelledby={titleId}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <figcaption className="min-w-0">
          <div id={titleId} className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            {title}
          </div>
          {subtitle && (
            <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
              {subtitle}
            </div>
          )}
        </figcaption>
        {table && !empty && (
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            aria-pressed={showTable}
            className="shrink-0 inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs cursor-pointer transition-colors hover:bg-[var(--viz-hover)] focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            style={{ color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
          >
            {showTable ? <BarChart3 size={12} aria-hidden="true" /> : <Table2 size={12} aria-hidden="true" />}
            {showTable ? 'Gráfico' : 'Tabela'}
          </button>
        )}
      </div>
      {empty ? (
        <EmptyState>{emptyText}</EmptyState>
      ) : showTable ? (
        <div className="overflow-x-auto max-h-80 overflow-y-auto">{table}</div>
      ) : (
        <>
          {legend}
          {children}
        </>
      )}
    </figure>
  );
}

/** Legend keyed like the marks (rect for bars, line for lines). */
export function Legend({ items }: { items: { label: string; color: string; shape?: 'rect' | 'line' }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 mb-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
      {items.map((item) => (
        <li key={item.label} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            style={{
              display: 'inline-block',
              width: item.shape === 'line' ? 14 : 10,
              height: item.shape === 'line' ? 2 : 10,
              borderRadius: item.shape === 'line' ? 1 : 2,
              background: item.color,
            }}
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

type VizTooltipProps = Partial<TooltipContentProps> & {
  labelFormat?: (label: unknown) => string;
  valueFormat?: (value: number) => string;
};

export function VizTooltip({
  active,
  payload,
  label,
  labelFormat = (l) => String(l ?? ''),
  valueFormat = fmtInt,
}: VizTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const rows = [...payload].reverse();
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-md)',
        minWidth: 140,
      }}
    >
      <div className="mb-1" style={{ color: 'var(--color-text-secondary)' }}>
        {labelFormat(label)}
      </div>
      {rows.map((row) => (
        <div key={String(row.dataKey ?? row.name)} className="flex items-center gap-2 py-0.5">
          <span
            aria-hidden="true"
            style={{
              display: 'inline-block',
              width: 12,
              height: 2,
              borderRadius: 1,
              background: String(row.color ?? row.fill ?? row.stroke ?? 'currentColor'),
            }}
          />
          <span className="font-semibold" style={{ color: 'var(--color-text)', fontVariantNumeric: 'tabular-nums' }}>
            {valueFormat(Number(row.value ?? 0))}
          </span>
          <span style={{ color: 'var(--color-text-secondary)' }}>{row.name}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Daily single-series area (small multiples share this)
// ---------------------------------------------------------------------------

interface DailyAreaProps {
  data: { day: string }[];
  dataKey: string;
  name: string;
  valueFormat?: (value: number) => string;
  height?: number;
}

export function DailyAreaChart({
  data,
  dataKey,
  name,
  valueFormat = fmtInt,
  height = 200,
}: DailyAreaProps) {
  const last = data.length - 1;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
        <XAxis
          dataKey="day"
          tickFormatter={fmtDayShort}
          tick={TICK}
          axisLine={AXIS_LINE}
          tickLine={false}
          minTickGap={28}
          interval="preserveStartEnd"
        />
        <YAxis
          allowDecimals={false}
          tickFormatter={(v: number) => fmtCompact(v)}
          tick={TICK}
          axisLine={false}
          tickLine={false}
          width={44}
        />
        <Tooltip
          cursor={{ stroke: 'var(--viz-axis)', strokeWidth: 1 }}
          content={(props) => <VizTooltip {...props} labelFormat={fmtDayLong} valueFormat={valueFormat} />}
          isAnimationActive={false}
        />
        <Area
          type="monotone"
          dataKey={dataKey}
          name={name}
          stroke="var(--viz-series-1)"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
          fill="var(--viz-series-1)"
          fillOpacity={0.1}
          isAnimationActive={false}
          dot={(props: { cx?: number; cy?: number; index?: number }) =>
            props.index === last && props.cx !== undefined && props.cy !== undefined ? (
              <circle
                key="end"
                cx={props.cx}
                cy={props.cy}
                r={4}
                fill="var(--viz-series-1)"
                stroke="var(--viz-surface)"
                strokeWidth={2}
              />
            ) : (
              <g key={`d${props.index}`} />
            )
          }
          activeDot={{ r: 4, fill: 'var(--viz-series-1)', stroke: 'var(--viz-surface)', strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Stacked daily columns (tokens in / out)
// ---------------------------------------------------------------------------

/** Rectangle with rounded top corners and a square base. */
function topRoundedRect(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.max(0, Math.min(r, w / 2, h));
  return [
    `M${x},${y + h}`,
    `L${x},${y + rr}`,
    `Q${x},${y} ${x + rr},${y}`,
    `L${x + w - rr},${y}`,
    `Q${x + w},${y} ${x + w},${y + rr}`,
    `L${x + w},${y + h}`,
    'Z',
  ].join(' ');
}

interface SegmentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  fill?: string;
  payload?: Record<string, number>;
}

/** Shape for a two-segment stack: gap above the lower one, rounded data end. */
function stackSegment(lowerKey: string, upperKey: string, segment: 'lower' | 'upper') {
  return function Segment({ x = 0, y = 0, width = 0, height = 0, fill, payload = {} }: SegmentProps) {
    if (width <= 0 || height <= 0) return <g />;
    const hasUpper = (payload[upperKey] ?? 0) > 0;
    const hasLower = (payload[lowerKey] ?? 0) > 0;
    // The upper segment gives up 2px at its base: the surface gap.
    const h = segment === 'upper' && hasLower ? Math.max(0, height - 2) : height;
    const rounded = segment === 'upper' || !hasUpper;
    return <path d={topRoundedRect(x, y, width, h, rounded ? 4 : 0)} fill={fill} />;
  };
}

interface StackedColumnsProps {
  data: { day: string }[];
  lower: { key: string; name: string };
  upper: { key: string; name: string };
  height?: number;
}

export function StackedDailyColumns({
  data,
  lower,
  upper,
  height = 220,
}: StackedColumnsProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: 0 }} barCategoryGap="22%">
        <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
        <XAxis
          dataKey="day"
          tickFormatter={fmtDayShort}
          tick={TICK}
          axisLine={AXIS_LINE}
          tickLine={false}
          minTickGap={28}
          interval="preserveStartEnd"
        />
        <YAxis
          allowDecimals={false}
          tickFormatter={(v: number) => fmtCompact(v)}
          tick={TICK}
          axisLine={false}
          tickLine={false}
          width={44}
        />
        <Tooltip
          cursor={{ fill: 'var(--viz-hover)' }}
          content={(props) => <VizTooltip {...props} labelFormat={fmtDayLong} />}
          isAnimationActive={false}
        />
        <Bar
          dataKey={lower.key}
          name={lower.name}
          stackId="stack"
          fill="var(--viz-series-1)"
          maxBarSize={24}
          isAnimationActive={false}
          shape={stackSegment(lower.key, upper.key, 'lower')}
        />
        <Bar
          dataKey={upper.key}
          name={upper.name}
          stackId="stack"
          fill="var(--viz-series-2)"
          maxBarSize={24}
          isAnimationActive={false}
          shape={stackSegment(lower.key, upper.key, 'upper')}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Ranked horizontal bars (one series → one hue)
// ---------------------------------------------------------------------------

export interface RankedRow {
  label: string;
  value: number;
}

export function RankedBars({ rows, name }: { rows: RankedRow[]; name: string }) {
  const height = rows.length * 30 + 12;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 52, bottom: 0, left: 0 }}>
        <XAxis type="number" hide domain={[0, 'dataMax']} />
        <YAxis
          type="category"
          dataKey="label"
          tick={{ ...TICK, fill: 'var(--color-text)' }}
          axisLine={AXIS_LINE}
          tickLine={false}
          width={184}
        />
        <Tooltip
          cursor={{ fill: 'var(--viz-hover)' }}
          content={(props) => <VizTooltip {...props} />}
          isAnimationActive={false}
        />
        <Bar
          dataKey="value"
          name={name}
          fill="var(--viz-series-1)"
          barSize={14}
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
        >
          <LabelList
            dataKey="value"
            position="right"
            formatter={(v: unknown) => fmtInt(Number(v ?? 0))}
            style={{ fill: 'var(--color-text-secondary)', fontSize: 11, fontVariantNumeric: 'tabular-nums' }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Install funnel (ordinal ramp, directly labeled)
// ---------------------------------------------------------------------------

export function FunnelSteps({ steps }: { steps: { label: string; value: number }[] }) {
  const first = steps[0]?.value ?? 0;
  const max = Math.max(1, ...steps.map((s) => s.value));
  return (
    <ol className="flex flex-col gap-2.5">
      {steps.map((step, i) => {
        const share = first > 0 ? step.value / first : null;
        return (
          <li key={step.label} className="grid grid-cols-[minmax(7rem,10rem)_1fr_auto] items-center gap-3 text-xs">
            <span style={{ color: 'var(--color-text)' }}>{step.label}</span>
            <span className="relative h-3.5 rounded-r" style={{ background: 'var(--viz-track)' }} aria-hidden="true">
              <span
                className="absolute inset-y-0 left-0 rounded-r"
                style={{
                  width: `${(step.value / max) * 100}%`,
                  minWidth: step.value > 0 ? 3 : 0,
                  background: `var(--viz-ord-${i + 1})`,
                }}
              />
            </span>
            <span className="text-right whitespace-nowrap" style={{ fontVariantNumeric: 'tabular-nums' }}>
              <span className="font-semibold" style={{ color: 'var(--color-text)' }}>
                {fmtInt(step.value)}
              </span>
              {i > 0 && share !== null && (
                <span className="ml-1.5" style={{ color: 'var(--color-text-secondary)' }}>
                  {fmtPercent(share)}
                </span>
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
