import React from "react";
import "./Button.css";
import { Spinner } from "./Spinner";

export const Button = ({
  children,
  variant = "primary",
  size = "md",
  fullWidth = false,
  isLoading = false,
  disabled = false,
  icon,
  className = "",
  ...props
}) => {
  const classes = [
    "btn",
    `btn-${variant}`,
    `btn-${size}`,
    fullWidth ? "btn-full" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button className={classes} disabled={disabled || isLoading} {...props}>
      {isLoading && <Spinner size={size === "lg" ? "md" : "sm"} />}
      {!isLoading && icon && <span className="btn-icon">{icon}</span>}
      <span>{children}</span>
    </button>
  );
};
