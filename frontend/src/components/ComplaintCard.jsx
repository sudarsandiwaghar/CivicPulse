import React from "react";
import { Link } from "react-router-dom";
import "./ComplaintCard.css";
import { StatusBadge } from "./StatusBadge";

export const ComplaintCard = ({
  id,
  complaintNumber,
  title,
  categoryName,
  status,
  priority,
  createdAt,
  className = "",
  showActionNotice = false,
}) => {
  const formattedDate = React.useMemo(() => {
    try {
      return new Date(createdAt).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return createdAt;
    }
  }, [createdAt]);

  const priorityColorClass = React.useMemo(() => {
    switch (priority) {
      case "CRITICAL":
        return "priority-critical";
      case "HIGH":
        return "priority-high";
      case "MEDIUM":
        return "priority-medium";
      case "LOW":
      default:
        return "priority-low";
    }
  }, [priority]);

  return (
    <div className={`complaint-card ${className} ${showActionNotice ? "action-highlight" : ""}`}>
      <div className="complaint-card-top">
        <div className="complaint-card-meta">
          <span className="complaint-card-number">{complaintNumber}</span>
          <span className="complaint-card-category">{categoryName}</span>
        </div>
        <div className="complaint-card-status">
          <StatusBadge status={status} />
        </div>
      </div>

      <h4 className="complaint-card-title">
        <Link to={`/citizen/complaints/${id}`}>{title}</Link>
      </h4>

      <div className="complaint-card-bottom">
        <div className="complaint-card-extra">
          {priority && (
            <span className={`complaint-priority-pill ${priorityColorClass}`}>
              {priority}
            </span>
          )}
          <span className="complaint-card-date">Submitted {formattedDate}</span>
        </div>

        <Link to={`/citizen/complaints/${id}`} className="complaint-card-link">
          {status === "RESOLVED_AWAITING_VERIFICATION" ? "Verify Now →" : "View Details →"}
        </Link>
      </div>
    </div>
  );
};
