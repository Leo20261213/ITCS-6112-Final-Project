import AssignmentBoard from "../components/AssignmentBoard";

// US-08: managers assign tickets to support agents
export default function ManagerPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Assignment board</h1>
          <p className="muted">Route each request to the right agent. Reassigned tickets move to that agent's queue right away.</p>
        </div>
      </div>
      <AssignmentBoard />
    </>
  );
}
