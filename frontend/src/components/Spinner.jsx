import React from "react";
import "./Spinner.css";

export const Spinner = ({
  size = "md",
  className = "",
  label = "Loading...",
}) => {
  return (
    <span
      className={`spinner spinner-${size} ${className}`}
      role="status"
      aria-label={label}
    />
  );
};
