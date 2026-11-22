import React from "react";
import "./StatCard.css";

export const StatCard = ({
  label,
  title,
  value,
  subtitle,
  change,
  changeType = "neutral",
  icon,
  className = "",
}) => {
  const displayLabel = label || title || "";
  const displaySub = subtitle || change;

  return (
    <div className={`stat-card ${className}`}>
      <div className="stat-card-info">
        <span className="stat-card-label">{displayLabel}</span>
        <span className="stat-card-value">{value}</span>
        {displaySub && (
          <span className={`stat-card-subtitle ${changeType ? `trend-${changeType}` : ""}`}>
            {displaySub}
          </span>
        )}
      </div>
      {icon && <div className="stat-card-icon">{icon}</div>}
    </div>
  );
};
