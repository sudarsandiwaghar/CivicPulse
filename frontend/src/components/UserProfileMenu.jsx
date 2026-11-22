import React from "react";
import "./UserProfileMenu.css";

export const UserProfileMenu = ({
  user,
  onLogout,
  className = "",
}) => {
  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((p) => p[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "U";

  const roleLabel =
    user?.role === "ADMINISTRATOR"
      ? "Administrator"
      : user?.role === "FIELD_WORKER"
      ? "Field Worker"
      : "Citizen";

  return (
    <div className={`user-profile-menu ${className}`}>
      <div className="user-avatar" title={user?.full_name}>
        {initials}
      </div>
      <div className="user-meta">
        <span className="user-name" title={user?.full_name}>
          {user?.full_name}
        </span>
        <span className="user-role-badge">{roleLabel}</span>
      </div>
      <button
        type="button"
        className="user-logout-btn"
        onClick={onLogout}
        title="Sign Out"
        aria-label="Sign Out"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <polyline points="16 17 21 12 16 7" />
          <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
        <span>Exit</span>
      </button>
    </div>
  );
};
