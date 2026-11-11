import { labels } from "../api";

export const StatusBadge = ({ value }) => <span className={`badge status-${value}`}>{labels[value]}</span>;
export const PriorityBadge = ({ value }) => <span className={`badge prio-${value}`}>{labels[value]}</span>;
