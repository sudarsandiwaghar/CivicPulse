import React from "react";
import "./ComplaintTimeline.css";

export const ComplaintTimeline = ({
  events,
  className = "",
}) => {
  if (!events || events.length === 0) {
    return (
      <div className="timeline-empty">
        <p>No timeline milestones recorded yet.</p>
      </div>
    );
  }

  const formatTimestamp = (dateStr) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const getEventIcon = (type) => {
    switch (type) {
      case "COMPLAINT_SUBMITTED":
        return (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        );
      case "ASSIGNMENT_CREATED":
      case "ASSIGNMENT_ACCEPTED":
        return (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
          </svg>
        );
      case "WORK_STARTED":
      case "PROGRESS_UPDATE":
        return (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        );
      case "WORK_COMPLETED":
        return (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        );
      case "COMPLAINT_CLOSED":
        return (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        );
      case "COMPLAINT_REOPENED":
        return (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          </svg>
        );
      default:
        return (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
          </svg>
        );
    }
  };

  return (
    <div className={`timeline-root ${className}`}>
      {events.map((ev, index) => (
        <div key={ev.id || index} className="timeline-item">
          <div className="timeline-marker">
            <div className="timeline-icon-box">{getEventIcon(ev.event_type)}</div>
            {index < events.length - 1 && <div className="timeline-line" />}
          </div>

          <div className="timeline-card">
            <div className="timeline-header">
              <span className="timeline-title">{ev.title}</span>
              <span className="timeline-time">{formatTimestamp(ev.timestamp)}</span>
            </div>

            <p className="timeline-desc">{ev.description}</p>

            {ev.actor && (
              <div className="timeline-actor">
                <span className="timeline-actor-role">{ev.actor.role}</span>
                <span className="timeline-actor-name">{ev.actor.name}</span>
              </div>
            )}

            {ev.remarks && (
              <div className="timeline-remarks">
                <strong>Notes:</strong> {ev.remarks}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
