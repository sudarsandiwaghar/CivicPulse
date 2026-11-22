import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { publicComplaintService } from "../services/publicComplaintService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Pagination } from "../components/Pagination";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { PublicComplaintCard } from "../components/PublicComplaintCard";

export const CitizenFollowingPage = () => {
  const navigate = useNavigate();

  const [followedItems, setFollowedItems] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);

  const fetchFollowed = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await publicComplaintService.getFollowedComplaints(page, pageSize);
      setFollowedItems(data.items);
      setTotalPages(data.total_pages);
      setTotalItems(data.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to load followed complaints. Please check your connection.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchFollowed();
  }, [fetchFollowed]);

  const handleUnfollow = async (complaintId) => {
    try {
      await publicComplaintService.unfollowComplaint(complaintId);
      setFeedback({ type: "success", text: "Successfully unfollowed complaint." });
      // Remove unfollowed item from local state
      setFollowedItems((prev) => prev.filter((item) => item.id !== complaintId));
      setTotalItems((prev) => Math.max(0, prev - 1));
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to unfollow.";
      setFeedback({ type: "error", text: msg });
    }
  };

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <div className="portal-phase-notice">
            <span>★</span> Community Watch
          </div>
          <h1 className="portal-header-title" style={{ marginTop: "var(--space-2)" }}>
            Followed Community Issues
          </h1>
          <p className="portal-header-subtitle">
            Stay informed on civic issues in your neighborhood that you are actively tracking
          </p>
        </div>
        <div className="portal-header-actions">
          <Button variant="outline" size="sm" onClick={() => navigate("/public-feed")}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
              <circle cx="12" cy="12" r="10" />
              <line x1="2" y1="12" x2="22" y2="12" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            Explore Public Feed
          </Button>
        </div>
      </div>

      {feedback && (
        <Alert variant={feedback.type === "success" ? "success" : "error"}>
          {feedback.text}
        </Alert>
      )}

      {error && (
        <Alert variant="error" title="Data Retrieval Notice">
          {error}
        </Alert>
      )}

      {/* Main Content */}
      <Card>
        <CardHeader>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <CardTitle>
              Followed Issues {totalItems > 0 && <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>({totalItems} active)</span>}
            </CardTitle>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              Page {page} of {totalPages || 1}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", padding: "var(--space-12) 0" }}>
              <Spinner size="md" />
              <span style={{ marginLeft: "var(--space-3)", color: "var(--color-text-muted)" }}>
                Loading followed complaints...
              </span>
            </div>
          ) : followedItems.length === 0 ? (
            <EmptyState
              icon={
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                </svg>
              }
              title="You are not following any community complaints yet"
              description="When you follow public issues reported by other citizens, you can monitor their progress and milestones right here."
              actionText="Browse Public Feed"
              onAction={() => navigate("/public-feed")}
            />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "var(--space-4)" }}>
                {followedItems.map((item) => (
                  <PublicComplaintCard
                    key={item.id}
                    complaint={item}
                    isFollowing
                    showUnfollowButton
                    onUnfollow={handleUnfollow}
                  />
                ))}
              </div>

              {totalPages > 1 && (
                <div style={{ marginTop: "var(--space-6)" }}>
                  <Pagination
                    currentPage={page}
                    totalPages={totalPages}
                    onPageChange={(newPage) => setPage(newPage)}
                  />
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
