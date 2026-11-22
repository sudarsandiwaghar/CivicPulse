import React from "react";
import "./TopHeader.css";
import { UserProfileMenu } from "./UserProfileMenu";
import { NotificationBell } from "./NotificationBell";

export const TopHeader = ({
  pageTitle = "Dashboard",
  user,
  onLogout,
  onToggleSidebar,
}) => {
  return (
    <header className="top-header">
      <div className="top-header-left">
        {onToggleSidebar && (
          <button
            type="button"
            className="mobile-menu-toggle"
            onClick={onToggleSidebar}
            aria-label="Toggle Sidebar Navigation"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        )}
        <h2 className="page-title">{pageTitle}</h2>
      </div>

      <div className="top-header-right">
        <div className="search-box-placeholder">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span>Search records...</span>
        </div>

        <NotificationBell />

        <UserProfileMenu user={user} onLogout={onLogout} />
      </div>
    </header>
  );
};
