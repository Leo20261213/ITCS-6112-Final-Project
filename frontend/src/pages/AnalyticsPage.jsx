import AnalyticsDashboard from "../components/AnalyticsDashboard";

// US-20: managers monitor support performance (administrators see it under Administration).
export default function AnalyticsPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Analytics</h1>
          <p className="muted">Ticket volume, status, and resolution trends.</p>
        </div>
      </div>
      <AnalyticsDashboard />
    </>
  );
}
