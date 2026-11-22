import React from "react";
import "./ComplaintStatusTracker.css";

const STEPS = [
  { id: "submitted", label: "Submitted", statuses: ["SUBMITTED"] },
  { id: "review", label: "Under Review", statuses: ["UNDER_REVIEW", "ON_HOLD"] },
  { id: "assigned", label: "Assigned", statuses: ["ASSIGNED"] },
  { id: "progress", label: "In Progress", statuses: ["IN_PROGRESS", "REOPENED"] },
  {
    id: "verification",
    label: "Resolved",
    statuses: ["RESOLVED_AWAITING_VERIFICATION"],
  },
  { id: "closed", label: "Closed & Verified", statuses: ["CLOSED"] },
];

export const ComplaintStatusTracker = ({
  status,
  className = "",
}) => {
  const isTerminalNegative = status === "REJECTED" || status === "DUPLICATE";

  // Determine current active step index (0 to 5)
  const getActiveStepIndex = () => {
    switch (status) {
      case "SUBMITTED":
        return 0;
      case "UNDER_REVIEW":
      case "ON_HOLD":
        return 1;
      case "ASSIGNED":
        return 2;
      case "IN_PROGRESS":
      case "REOPENED":
        return 3;
      case "RESOLVED_AWAITING_VERIFICATION":
        return 4;
      case "CLOSED":
        return 5;
      case "REJECTED":
      case "DUPLICATE":
        return 1; // halted at review
      default:
        return 0;
    }
  };

  const activeIndex = getActiveStepIndex();

  return (
    <div className={`status-tracker-root ${className}`}>
      {isTerminalNegative ? (
        <div className="tracker-special-status">
          <div className="tracker-special-badge negative">
            <span>●</span> Status: {status === "REJECTED" ? "Rejected by Municipal Review" : "Marked Duplicate"}
          </div>
          <p className="tracker-special-desc">
            This complaint was concluded during review and is no longer moving through active resolution.
          </p>
        </div>
      ) : (
        <div className="tracker-stepper">
          {STEPS.map((step, idx) => {
            const isCompleted = idx < activeIndex;
            const isCurrent = idx === activeIndex;

            let stepStateClass = "pending";
            if (isCompleted) stepStateClass = "completed";
            if (isCurrent) stepStateClass = "current";

            return (
              <div key={step.id} className={`tracker-step ${stepStateClass}`}>
                <div className="tracker-step-indicator">
                  <div className="tracker-step-circle">
                    {isCompleted ? (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    ) : (
                      <span>{idx + 1}</span>
                    )}
                  </div>
                  {idx < STEPS.length - 1 && <div className="tracker-step-connector" />}
                </div>
                <div className="tracker-step-label">{step.label}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
