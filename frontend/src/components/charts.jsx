import { useEffect, useRef, useState } from "react";

/* Small SVG chart kit for the analytics dashboard (US-20).
   Marks: 2px lines, >=8px end dots with a 2px surface ring, bars <=24px thick with a 4px
   rounded data-end, hairline solid gridlines. Text always uses text colours; colour lives
   only on the marks. Every chart has a hover/focus readout and a table view. */

const fmt = (n) => (n == null ? "—" : Number.isInteger(n) ? n.toLocaleString() : n.toLocaleString(undefined, { maximumFractionDigits: 1 }));

function useWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

function niceMax(max) {
  if (max <= 4) return 4;
  const pow = 10 ** Math.floor(Math.log10(max));
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (step * pow >= max) return step * pow;
  }
  return 10 * pow;
}

function ticks(max, count = 4) {
  const step = max / count;
  return Array.from({ length: count + 1 }, (_, i) => Math.round(i * step * 100) / 100);
}

export function ChartCard({ title, subtitle, children, table, wide = false }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section className={`card chart-card${wide ? " wide" : ""}`}>
      <div className="chart-head">
        <div>
          <h3>{title}</h3>
          {subtitle && <p className="muted small">{subtitle}</p>}
        </div>
        {table && (
          <button className="link-btn small" onClick={() => setShowTable((s) => !s)} aria-pressed={showTable}>
            {showTable ? "Show chart" : "Show table"}
          </button>
        )}
      </div>
      {showTable ? table : children}
    </section>
  );
}

export function DataTable({ columns, rows }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>{columns.map((c) => <th key={c.key} className={c.num ? "num" : ""}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => <td key={c.key} className={c.num ? "num" : ""}>{c.num ? fmt(r[c.key]) : r[c.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Legend({ series, kind = "line" }) {
  return (
    <ul className="legend">
      {series.map((s) => (
        <li key={s.key}>
          <span className={`key key-${kind}`} style={{ background: s.color }} aria-hidden />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

/** Multi-series line chart over an ordered x (dates). One y-axis, crosshair readout. */
export function LineChart({ data, series, xLabel, height = 240, ariaLabel }) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);
  const m = { top: 12, right: 92, bottom: 28, left: 36 };
  const w = Math.max(0, width - m.left - m.right);
  const h = height - m.top - m.bottom;
  const max = niceMax(Math.max(1, ...data.flatMap((d) => series.map((s) => d[s.key]))));
  const x = (i) => (data.length <= 1 ? w / 2 : (i / (data.length - 1)) * w);
  const y = (v) => h - (v / max) * h;
  const every = Math.max(1, Math.ceil(data.length / Math.max(2, Math.floor(w / 72))));
  const last = data.length - 1;

  const ends = series.map((s) => ({ ...s, v: data[last]?.[s.key] ?? 0 })).map((s) => ({ ...s, yy: y(s.v) }));
  const endsFit = ends.every((a, i) => ends.every((b, j) => i === j || Math.abs(a.yy - b.yy) >= 16));

  const pick = (clientX, rect) => {
    const px = clientX - rect.left - m.left;
    setHover(Math.max(0, Math.min(last, Math.round((px / Math.max(1, w)) * last))));
  };
  const onKey = (e) => {
    if (e.key === "ArrowRight") setHover((i) => Math.min(last, (i ?? -1) + 1));
    else if (e.key === "ArrowLeft") setHover((i) => Math.max(0, (i ?? last + 1) - 1));
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };

  return (
    <div className="chart" ref={ref}>
      <Legend series={series} />
      {width > 0 && (
        <div className="plot" style={{ height }}>
          <svg
            width={width}
            height={height}
            role="img"
            aria-label={ariaLabel}
            tabIndex={0}
            onKeyDown={onKey}
            onBlur={() => setHover(null)}
            onPointerMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
            onPointerLeave={() => setHover(null)}
          >
            <g transform={`translate(${m.left},${m.top})`}>
              {ticks(max).map((t) => (
                <g key={t}>
                  <line className="grid" x1={0} x2={w} y1={y(t)} y2={y(t)} />
                  <text className="tick" x={-8} y={y(t)} dy="0.32em" textAnchor="end">{fmt(t)}</text>
                </g>
              ))}
              <line className="baseline" x1={0} x2={w} y1={h} y2={h} />
              {data.map((d, i) =>
                i % every === 0 || i === last ? (
                  <text key={i} className="tick" x={x(i)} y={h + 18} textAnchor={i === 0 ? "start" : i === last ? "end" : "middle"}>
                    {xLabel(d)}
                  </text>
                ) : null
              )}
              {hover != null && <line className="crosshair" x1={x(hover)} x2={x(hover)} y1={0} y2={h} />}
              {series.map((s) => (
                <path
                  key={s.key}
                  d={data.map((d, i) => `${i ? "L" : "M"}${x(i)},${y(d[s.key])}`).join("")}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              ))}
              {ends.map((s) => (
                <circle key={s.key} cx={x(last)} cy={s.yy} r={4} fill={s.color} className="ring" />
              ))}
              {hover != null &&
                series.map((s) => (
                  <circle key={s.key} cx={x(hover)} cy={y(data[hover][s.key])} r={4.5} fill={s.color} className="ring" />
                ))}
              {endsFit &&
                ends.map((s) => (
                  <text key={s.key} className="end-label" x={x(last) + 10} y={s.yy} dy="0.32em">
                    {s.label} <tspan className="end-value">{fmt(s.v)}</tspan>
                  </text>
                ))}
            </g>
          </svg>
          {hover != null && (
            <div
              className="tooltip"
              style={{ left: Math.min(m.left + x(hover) + 12, width - 150), top: 8 }}
              role="status"
            >
              <div className="tooltip-title">{xLabel(data[hover], true)}</div>
              {series.map((s) => (
                <div key={s.key} className="tooltip-row">
                  <span className="key key-line" style={{ background: s.color }} aria-hidden />
                  <b>{fmt(data[hover][s.key])}</b>
                  <span className="muted">{s.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Single-series vertical columns. Null values draw nothing (no data that week). */
export function ColumnChart({ data, valueKey, xLabel, color, unit = "", height = 220, ariaLabel, describe }) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);
  const m = { top: 20, right: 8, bottom: 28, left: 36 };
  const w = Math.max(0, width - m.left - m.right);
  const h = height - m.top - m.bottom;
  const values = data.map((d) => d[valueKey]);
  const max = niceMax(Math.max(1, ...values.filter((v) => v != null)));
  const band = w / Math.max(1, data.length);
  const bw = Math.min(24, band * 0.6);
  const y = (v) => h - (v / max) * h;
  const peak = values.reduce((best, v, i) => (v != null && (best < 0 || v > values[best]) ? i : best), -1);

  return (
    <div className="chart" ref={ref}>
      {width > 0 && (
        <div className="plot" style={{ height }}>
          <svg width={width} height={height} role="img" aria-label={ariaLabel}>
            <g transform={`translate(${m.left},${m.top})`}>
              {ticks(max).map((t) => (
                <g key={t}>
                  <line className="grid" x1={0} x2={w} y1={y(t)} y2={y(t)} />
                  <text className="tick" x={-8} y={y(t)} dy="0.32em" textAnchor="end">{fmt(t)}</text>
                </g>
              ))}
              <line className="baseline" x1={0} x2={w} y1={h} y2={h} />
              {data.map((d, i) => {
                const v = d[valueKey];
                const cx = band * i + band / 2;
                const top = v == null ? h : y(v);
                const r = Math.min(4, (h - top) / 2);
                return (
                  <g
                    key={i}
                    tabIndex={0}
                    className={`col${hover === i ? " active" : ""}`}
                    onPointerEnter={() => setHover(i)}
                    onPointerLeave={() => setHover(null)}
                    onFocus={() => setHover(i)}
                    onBlur={() => setHover(null)}
                    aria-label={describe(d)}
                  >
                    <rect className="hit" x={band * i} y={0} width={band} height={h} />
                    {v != null && v > 0 && (
                      <path
                        fill={color}
                        d={`M${cx - bw / 2},${h}V${top + r}Q${cx - bw / 2},${top} ${cx - bw / 2 + r},${top}H${cx + bw / 2 - r}Q${cx + bw / 2},${top} ${cx + bw / 2},${top + r}V${h}Z`}
                      />
                    )}
                    {(i === peak || hover === i) && v != null && (
                      <text className="cap-label" x={cx} y={top - 6} textAnchor="middle">{fmt(v)}{unit}</text>
                    )}
                    <text className="tick" x={cx} y={h + 18} textAnchor="middle">{xLabel(d)}</text>
                  </g>
                );
              })}
            </g>
          </svg>
          {hover != null && (
            <div className="tooltip" style={{ left: Math.min(m.left + band * hover + band / 2 + 12, width - 170), top: 8 }} role="status">
              {describe(data[hover])}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Horizontal bars, one series, value at the tip. */
export function BarList({ rows, color, ariaLabel, valueSuffix = "" }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  const total = rows.reduce((s, r) => s + r.count, 0);
  return (
    <ul className="barlist" aria-label={ariaLabel}>
      {rows.map((r) => (
        <li key={r.key} tabIndex={0} title={`${r.label}: ${r.count}${valueSuffix} (${total ? Math.round((100 * r.count) / total) : 0}% of ${total})`}>
          <span className="bar-label">{r.label}</span>
          <span className="bar-track">
            {r.count > 0 && <span className="bar" style={{ width: `${(r.count / max) * 100}%`, background: color }} />}
            <span className="bar-value">{fmt(r.count)}{valueSuffix}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function StatTile({ label, value, sub, delta }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {(delta || sub) && (
        <div className="stat-sub">
          {delta && <span className={`delta ${delta.tone}`}>{delta.text}</span>}
          {sub && <span className="muted">{sub}</span>}
        </div>
      )}
    </div>
  );
}
