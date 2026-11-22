import React from "react";

const PRIORITY_STYLES = {
  CRITICAL: {
    bg: "#fee2e2",
    color: "#991b1b",
    border: "#fca5a5",
  },
  URGENT: {
    bg: "#fee2e2",
    color: "#991b1b",
    border: "#fca5a5",
  },
  HIGH: {
    bg: "#fef3c7",
    color: "#92400e",
    border: "#fcd34d",
  },
  MEDIUM: {
    bg: "#e0f2fe",
    color: "#075985",
    border: "#bae6fd",
  },
  LOW: {
    bg: "#f1f5f9",
    color: "#475569",
    border: "#cbd5e1",
  },
};

export const PriorityBadge = ({ priority = "MEDIUM", size = "md" }) => {
  const normKey = (priority || "MEDIUM").toUpperCase();
  const style = PRIORITY_STYLES[normKey] || PRIORITY_STYLES.MEDIUM;

  const isSmall = size === "sm";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: isSmall ? "1px 6px" : "2px 8px",
        borderRadius: "var(--radius-sm)",
        fontSize: isSmall ? "0.6875rem" : "var(--text-xs)",
        fontWeight: 700,
        textTransform: "uppercase",
        backgroundColor: style.bg,
        color: style.color,
        border: `1px solid ${style.border}`,
        lineHeight: 1.2,
      }}
    >
      {priority}
    </span>
  );
};

export default PriorityBadge;
