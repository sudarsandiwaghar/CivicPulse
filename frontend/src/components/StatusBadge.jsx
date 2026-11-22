import React from "react";
import "./StatusBadge.css";

const STATUS_LABELS = {
  SUBMITTED: "Submitted",
  UNDER_REVIEW: "Under Review",
  ASSIGNED: "Assigned",
  IN_PROGRESS: "In Progress",
  RESOLVED_AWAITING_VERIFICATION: "Resolved (Awaiting Verification)",
  CLOSED: "Closed",
  REJECTED: "Rejected",
  ON_HOLD: "On Hold",
  REOPENED: "Reopened",
};

export const StatusBadge = ({
  status,
  className = "",
  showDot = true,
}) => {
  const normKey = (status || "").toUpperCase();
  const label = STATUS_LABELS[normKey] || status;
  const modifier = (status || "").toLowerCase().replace(/\s+/g, "_");

  return (
    <span className={`status-badge status-${modifier} ${className}`}>
      {showDot && <span className="status-badge-dot" />}
      <span>{label}</span>
    </span>
  );
};
