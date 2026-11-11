import { Navigate, Route, Routes } from "react-router-dom";
import { homeFor, useAuth } from "./auth";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import MyTicketsPage from "./pages/MyTicketsPage";
import NewTicketPage from "./pages/NewTicketPage";
import TicketDetailPage from "./pages/TicketDetailPage";
import AgentQueuePage from "./pages/AgentQueuePage";
import AdminPage from "./pages/AdminPage";

// US-02: client-side guard mirrors the server's role checks so users only see features they may use.
function RequireRole({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center muted">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/forbidden" replace />;
  return children;
}

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <div className="center muted">Loading…</div>;
  return <Navigate to={user ? homeFor(user.role) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<RequireRole><Layout /></RequireRole>}>
        <Route path="/tickets" element={<RequireRole roles={["end_user"]}><MyTicketsPage /></RequireRole>} />
        <Route path="/tickets/new" element={<RequireRole roles={["end_user"]}><NewTicketPage /></RequireRole>} />
        <Route path="/tickets/:id" element={<TicketDetailPage />} />
        <Route path="/queue" element={<RequireRole roles={["agent"]}><AgentQueuePage /></RequireRole>} />
        <Route path="/admin" element={<RequireRole roles={["admin"]}><AdminPage /></RequireRole>} />
        <Route
          path="/forbidden"
          element={
            <div className="card empty">
              <h2>Access denied</h2>
              <p className="muted">Your role does not have permission to use that feature.</p>
            </div>
          }
        />
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  );
}
