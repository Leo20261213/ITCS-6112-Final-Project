import TicketTable from "../components/TicketTable";

// US-06: support agents view tickets assigned to them
export default function AgentQueuePage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>My queue</h1>
          <p className="muted">Tickets assigned to you. Open one to update its status.</p>
        </div>
      </div>
      <TicketTable showRequester emptyText="No tickets assigned to you match these filters." />
    </>
  );
}
