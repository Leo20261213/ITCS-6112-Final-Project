import { useEffect, useState } from "react";
import { api } from "../api";
import { BarList, ChartCard, ColumnChart, DataTable, LineChart, StatTile } from "./charts";

// Validated categorical slots 1-2 (blue, orange) on the white card surface.
const SERIES = [
  { key: "created", label: "Created", color: "var(--series-1)" },
  { key: "resolved", label: "Resolved", color: "var(--series-2)" },
];
const RANGES = [
  [7, "Last 7 days"],
  [30, "Last 30 days"],
  [90, "Last 90 days"],
];

const day = (iso, long = false) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, long ? { weekday: "short", month: "short", day: "numeric" } : { month: "short", day: "numeric" });

const hours = (h) => {
  if (h == null) return "—";
  if (h < 1) return `${Math.round(h * 60)} min`;
  if (h < 48) return `${h.toFixed(h < 10 ? 1 : 0)} h`;
  return `${(h / 24).toFixed(1)} days`;
};

// US-20: ticket volumes, statuses, and resolution trends.
export default function AnalyticsDashboard() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api(`/analytics?days=${days}`)
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [days]);

  if (!data) {
    return error ? <div className="alert error">{error}</div> : <p className="muted">Loading analytics…</p>;
  }

  const t = data.totals;
  const change = t.created_change_pct;
  const delta =
    change == null
      ? null
      : { text: `${change > 0 ? "▲" : change < 0 ? "▼" : "■"} ${Math.abs(change)}% vs previous ${days} days`, tone: "neutral" };

  return (
    <div className={`dashboard${loading ? " refreshing" : ""}`}>
      <div className="filters dash-filters">
        <label className="inline-label">
          <span className="sr-only">Date range</span>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Date range">
            {RANGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <span className="muted small">{day(data.start)} – {day(data.end)}</span>
        {error && <span className="alert error inline">{error}</span>}
      </div>

      <div className="stats">
        <StatTile label="Tickets created" value={t.created.toLocaleString()} delta={delta} />
        <StatTile label="Tickets resolved" value={t.resolved.toLocaleString()} sub={t.resolved_within_24h_pct != null ? `${t.resolved_within_24h_pct}% within 24 h` : "None yet"} />
        <StatTile label="Median time to resolve" value={hours(t.median_resolution_hours)} sub="From submission to resolved" />
        <StatTile
          label="Open backlog"
          value={t.open_backlog.toLocaleString()}
          sub={`${t.critical_open} critical · ${t.unassigned} unassigned`}
        />
      </div>

      <div className="chart-grid">
        <ChartCard
          wide
          title="Tickets created and resolved per day"
          subtitle="Volume coming in against work going out"
          table={
            <DataTable
              columns={[{ key: "date", label: "Date" }, { key: "created", label: "Created", num: true }, { key: "resolved", label: "Resolved", num: true }]}
              rows={data.daily.map((d) => ({ ...d, date: day(d.date, true) }))}
            />
          }
        >
          <LineChart
            data={data.daily}
            series={SERIES}
            xLabel={(d, long) => day(d.date, long)}
            ariaLabel={`Line chart of tickets created and resolved per day over the last ${days} days. Use the arrow keys to read values.`}
          />
        </ChartCard>

        <ChartCard
          title="Resolution time trend"
          subtitle="Median hours to resolve, by week resolved"
          table={
            <DataTable
              columns={[{ key: "week", label: "Week of" }, { key: "resolved", label: "Resolved", num: true }, { key: "median_resolution_hours", label: "Median hours", num: true }]}
              rows={data.weekly.map((w) => ({ ...w, week: day(w.week_start) }))}
            />
          }
        >
          <ColumnChart
            data={data.weekly}
            valueKey="median_resolution_hours"
            color="var(--series-1)"
            unit=" h"
            xLabel={(w) => day(w.week_start)}
            ariaLabel="Column chart of median resolution time per week"
            describe={(w) =>
              w.median_resolution_hours == null
                ? `Week of ${day(w.week_start)}: no tickets resolved`
                : `Week of ${day(w.week_start)}: median ${hours(w.median_resolution_hours)} across ${w.resolved} resolved`
            }
          />
        </ChartCard>

        <ChartCard
          title="Current status"
          subtitle="All tickets, right now"
          table={<DataTable columns={[{ key: "label", label: "Status" }, { key: "count", label: "Tickets", num: true }]} rows={data.by_status} />}
        >
          <BarList rows={data.by_status} color="var(--series-1)" ariaLabel="Tickets by current status" />
        </ChartCard>

        <ChartCard
          title="Created by priority"
          subtitle={`Last ${days} days`}
          table={
            <DataTable
              columns={[{ key: "label", label: "Priority" }, { key: "count", label: "Created", num: true }, { key: "median", label: "Median time to resolve" }]}
              rows={data.by_priority.map((p) => ({ ...p, median: hours(p.median_resolution_hours) }))}
            />
          }
        >
          <BarList rows={data.by_priority} color="var(--series-1)" ariaLabel="Tickets created by priority" />
          <p className="muted small chart-note">
            Median time to resolve:{" "}
            {data.by_priority.map((p, i) => (
              <span key={p.key}>{i > 0 && " · "}{p.label} {hours(p.median_resolution_hours)}</span>
            ))}
          </p>
        </ChartCard>

        <ChartCard
          title="Created by category"
          subtitle={`Last ${days} days`}
          table={<DataTable columns={[{ key: "label", label: "Category" }, { key: "count", label: "Created", num: true }]} rows={data.by_category} />}
        >
          {data.by_category.length ? (
            <BarList rows={data.by_category} color="var(--series-1)" ariaLabel="Tickets created by category" />
          ) : (
            <p className="muted small">No tickets created in this period.</p>
          )}
        </ChartCard>
      </div>

      <section className="card">
        <h3>Agent workload and performance</h3>
        <DataTable
          columns={[
            { key: "name", label: "Agent" },
            { key: "active", label: "Active now", num: true },
            { key: "resolved", label: `Resolved (${days} d)`, num: true },
            { key: "median", label: "Median time to resolve" },
          ]}
          rows={data.agents.map((a) => ({ ...a, median: hours(a.median_resolution_hours) }))}
        />
      </section>
    </div>
  );
}
