import React from "react";
import "./ComplaintMap.css";
import { STATUS_COLORS } from "./mapConstants";

export const MapLegend = ({ counts = {} }) => {
  const items = [
    { label: "Pending Triage", color: STATUS_COLORS.SUBMITTED, count: counts.SUBMITTED },
    { label: "Under Review", color: STATUS_COLORS.UNDER_REVIEW, count: counts.UNDER_REVIEW },
    { label: "Assigned", color: STATUS_COLORS.ASSIGNED, count: counts.ASSIGNED },
    { label: "In Progress", color: STATUS_COLORS.IN_PROGRESS, count: counts.IN_PROGRESS },
    { label: "On Hold", color: STATUS_COLORS.ON_HOLD, count: counts.ON_HOLD },
    { label: "Resolved", color: STATUS_COLORS.RESOLVED_AWAITING_VERIFICATION, count: counts.RESOLVED_AWAITING_VERIFICATION },
    { label: "Closed", color: STATUS_COLORS.CLOSED, count: counts.CLOSED },
  ];

  return (
    <div className="map-legend">
      <span style={{ fontWeight: 700, color: "var(--color-text-main)", textTransform: "uppercase", fontSize: "0.6875rem" }}>
        Status Legend:
      </span>
      {items.map((item) => (
        <div key={item.label} className="map-legend-item">
          <span className="map-legend-dot" style={{ backgroundColor: item.color }} />
          <span>
            {item.label}
            {typeof item.count === "number" ? ` (${item.count})` : ""}
          </span>
        </div>
      ))}
    </div>
  );
};

export default MapLegend;
