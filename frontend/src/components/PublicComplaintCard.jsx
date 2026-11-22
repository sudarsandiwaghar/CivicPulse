import React from "react";
import { Link } from "react-router-dom";
import "./PublicComplaintCard.css";
import { StatusBadge } from "./StatusBadge";

export const PublicComplaintCard = ({
  complaint,
  className = "",
  isFollowing = false,
  onUnfollow,
  showUnfollowButton = false,
}) => {
  const formattedDate = React.useMemo(() => {
    try {
      return new Date(complaint.created_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return complaint.created_at;
    }
  }, [complaint.created_at]);

  const locationLabel = React.useMemo(() => {
    const parts = [];
    if (complaint.ward_or_district) parts.push(complaint.ward_or_district);
    if (complaint.city) parts.push(complaint.city);
    return parts.length > 0 ? parts.join(", ") : "Municipal District";
  }, [complaint.ward_or_district, complaint.city]);

  return (
    <div className={`public-complaint-card ${className}`}>
      <div className="public-card-header">
        <div className="public-card-tags">
          <span className="public-card-code">{complaint.complaint_number}</span>
          <span className="public-card-category">{complaint.category_name}</span>
          {isFollowing && <span className="public-card-following-badge">★ Following</span>}
        </div>
        <StatusBadge status={complaint.status} />
      </div>

      <h3 className="public-card-title">
        <Link to={`/public-feed/${complaint.id}`}>{complaint.public_title}</Link>
      </h3>

      <p className="public-card-desc">{complaint.public_description}</p>

      <div className="public-card-footer">
        <div className="public-card-meta">
          <span className="public-card-location">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            {locationLabel}
          </span>
          <span className="public-card-date">Published {formattedDate}</span>
        </div>

        <div className="public-card-actions">
          {showUnfollowButton && onUnfollow && (
            <button
              type="button"
              className="public-card-unfollow-btn"
              onClick={() => onUnfollow(complaint.id)}
            >
              Unfollow
            </button>
          )}
          <Link to={`/public-feed/${complaint.id}`} className="public-card-link">
            View Updates →
          </Link>
        </div>
      </div>
    </div>
  );
};
