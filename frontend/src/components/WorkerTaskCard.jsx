import React from "react";
import { Link } from "react-router-dom";
import "./WorkerTaskCard.css";
import { StatusBadge } from "./StatusBadge";
import { Button } from "./Button";

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export const WorkerTaskCard = ({
  task,
  onAccept,
  onStart,
  actionLoading = false,
  className = "",
}) => {
  const isPendingAcceptance =
    task.assignment_status === "ASSIGNED" && !task.accepted_at;
  const isAcceptedPendingStart =
    task.assignment_status === "ASSIGNED" && Boolean(task.accepted_at);
  const isInProgress = task.assignment_status === "IN_PROGRESS";
  const isCompleted = task.assignment_status === "COMPLETED";

  // Derive card border styling
  let borderClass = "";
  if (isPendingAcceptance) {
    borderClass = "action-required";
  } else if (isInProgress) {
    borderClass = "in-progress-border";
  } else if (isCompleted) {
    borderClass = "completed-border";
  }

  // Priority CSS class
  const priorityClass = `priority-${(task.priority || "medium").toLowerCase()}`;

  // Formatted location string
  const locationText = task.location
    ? [
        task.location.address_line1,
        task.location.landmark,
        task.location.ward_or_district,
        task.location.city,
      ]
        .filter(Boolean)
        .join(", ")
    : "Municipal Sector Area";

  return (
    <div className={`worker-task-card ${borderClass} ${className}`}>
      {/* Top Metadata Header */}
      <div className="task-card-header">
        <div className="task-card-meta">
          <span className="task-number-badge">
            {task.complaint_number || "TASK"}
          </span>
          {task.category_name && (
            <span className="task-category-pill">{task.category_name}</span>
          )}
          {task.priority && (
            <span className={`task-priority-pill ${priorityClass}`}>
              {task.priority}
            </span>
          )}
        </div>

        {/* Operational Stage Badge */}
        <div>
          {isPendingAcceptance && (
            <span className="task-stage-badge task-stage-pending-accept">
              <span>●</span> Awaiting Acceptance
            </span>
          )}
          {isAcceptedPendingStart && (
            <span className="task-stage-badge task-stage-accepted">
              <span>✓</span> Accepted (Ready to Start)
            </span>
          )}
          {isInProgress && (
            <span className="task-stage-badge task-stage-in-progress">
              <span>⚙</span> Work In Progress
            </span>
          )}
          {isCompleted && (
            <span className="task-stage-badge task-stage-completed">
              <span>★</span> Completed
            </span>
          )}
          {task.assignment_status === "REASSIGNED" && (
            <span className="task-stage-badge task-stage-reassigned">
              Reassigned
            </span>
          )}
        </div>
      </div>

      {/* Title & Description */}
      <h3 className="task-card-title">
        <Link to={`/worker/tasks/${task.assignment_id}`}>{task.title}</Link>
      </h3>
      {task.description && (
        <p className="task-card-desc">{task.description}</p>
      )}

      {/* Location */}
      <div className="task-card-location">
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
          <circle cx="12" cy="10" r="3" />
        </svg>
        <span>{locationText}</span>
      </div>

      {/* Card Footer & Action Buttons */}
      <div className="task-card-footer">
        <div className="task-card-timestamps">
          <span>Assigned: {formatDate(task.assigned_at) || "N/A"}</span>
          {task.started_at && (
            <span>Started: {formatDate(task.started_at)}</span>
          )}
          {task.completed_at && (
            <span>Completed: {formatDate(task.completed_at)}</span>
          )}
          <StatusBadge status={task.complaint_status} />
        </div>

        <div className="task-card-actions">
          {/* Quick Accept Action */}
          {isPendingAcceptance && onAccept && (
            <Button
              variant="outline"
              size="sm"
              disabled={actionLoading}
              onClick={() => onAccept(task.assignment_id)}
            >
              Accept
            </Button>
          )}

          {/* Quick Start Action */}
          {isAcceptedPendingStart && onStart && (
            <Button
              variant="primary"
              size="sm"
              disabled={actionLoading}
              onClick={() => onStart(task.assignment_id)}
            >
              Start Work
            </Button>
          )}

          <Link to={`/worker/tasks/${task.assignment_id}`}>
            <Button variant="secondary" size="sm">
              View Work Order &rarr;
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
};
