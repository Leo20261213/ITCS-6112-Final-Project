import { Link } from "react-router-dom";
import TicketTable from "../components/TicketTable";

// US-04: end users view their submitted tickets
export default function MyTicketsPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>My tickets</h1>
          <p className="muted">Track the progress of the requests you have submitted.</p>
        </div>
        <Link to="/tickets/new" className="btn primary">Submit a ticket</Link>
      </div>
      <TicketTable showAssignee emptyText="You have not submitted any tickets that match." />
    </>
  );
}
