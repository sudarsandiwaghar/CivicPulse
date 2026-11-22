import React, { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { publicComplaintService } from "../services/publicComplaintService";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { StatusBadge } from "../components/StatusBadge";
import { Alert } from "../components/Alert";
import { Spinner } from "../components/Spinner";
import { ConfirmationDialog } from "../components/ConfirmationDialog";

export const PublicComplaintDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  const [complaint, setComplaint] = useState(null);
  const [isFollowing, setIsFollowing] = useState(false);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Follow Action State
  const [isFollowLoading, setIsFollowLoading] = useState(false);
  const [followMessage, setFollowMessage] = useState(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  const fetchDetail = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await publicComplaintService.getPublicComplaintDetail(id);
      setComplaint(data);

      // If user is an authenticated citizen, check if they already follow this complaint
      if (isAuthenticated && user?.role === "CITIZEN") {
        try {
          const followedFeed = await publicComplaintService.getFollowedComplaints(1, 50);
          const alreadyFollowing = followedFeed.items.some((item) => item.id === id);
          setIsFollowing(alreadyFollowing);
        } catch {
          // Non-blocking follow check
        }
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.statusCode === 404) {
          setError(
            "This complaint record is either private, unpublished, or does not exist."
          );
        } else {
          setError(err.message);
        }
      } else {
        setError("Unable to load public complaint details. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [id, isAuthenticated, user]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const handleToggleFollow = async () => {
    if (!id) return;

    if (!isAuthenticated || !user) {
      setIsAuthModalOpen(true);
      return;
    }

    if (user.role !== "CITIZEN") {
      setFollowMessage({
        type: "error",
        text: "Community following is available for verified citizen accounts only.",
      });
      return;
    }

    setIsFollowLoading(true);
    setFollowMessage(null);
    try {
      if (isFollowing) {
        const res = await publicComplaintService.unfollowComplaint(id);
        setIsFollowing(false);
        setFollowMessage({ type: "success", text: res.message || "Unfollowed complaint." });
      } else {
        const res = await publicComplaintService.followComplaint(id);
        setIsFollowing(true);
        setFollowMessage({ type: "success", text: res.message || "Now following complaint updates." });
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to update follow status.";
      setFollowMessage({ type: "error", text: msg });
    } finally {
      setIsFollowLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "N/A";
    try {
      return new Date(dateStr).toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  if (isLoading) {
    return (
      <div className="container" style={{ padding: "var(--space-16) 0", display: "flex", flexDirection: "column", alignItems: "center" }}>
        <Spinner size="lg" />
        <span style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)" }}>
          Loading public complaint details...
        </span>
      </div>
    );
  }

  if (error || !complaint) {
    return (
      <div className="container" style={{ maxWidth: "700px", padding: "var(--space-12) var(--space-4)" }}>
        <Alert variant="error" title="Complaint Unavailable">
          {error || "The requested public complaint could not be found."}
        </Alert>
        <div style={{ marginTop: "var(--space-6)", textAlign: "center" }}>
          <Link to="/public-feed">
            <Button variant="primary">Return to Public Feed</Button>
          </Link>
        </div>
      </div>
    );
  }

  const locationDisplay = [complaint.ward_or_district, complaint.city].filter(Boolean).join(", ") || "General Municipal Area";

  return (
    <div className="container" style={{ maxWidth: "860px", padding: "var(--space-8) var(--space-4)" }}>
      {/* Navigation Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
        <Link to="/public-feed" style={{ fontSize: "var(--text-sm)", color: "var(--color-primary)", fontWeight: "600" }}>
          ← Back to Public Community Feed
        </Link>
        <span style={{ color: "var(--color-text-muted)" }}>/</span>
        <span style={{ fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
          {complaint.complaint_number}
        </span>
      </div>

      {followMessage && (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <Alert variant={followMessage.type === "success" ? "success" : "error"}>
            {followMessage.text}
          </Alert>
        </div>
      )}

      {/* Main Details Card */}
      <Card style={{ marginBottom: "var(--space-6)" }}>
        <CardHeader>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-4)", flexWrap: "wrap", width: "100%" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)", flexWrap: "wrap" }}>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--text-xs)",
                    fontWeight: "bold",
                    color: "var(--color-primary)",
                    backgroundColor: "var(--color-bg-active-nav)",
                    padding: "3px 8px",
                    borderRadius: "var(--radius-sm)",
                  }}
                >
                  {complaint.complaint_number}
                </span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {complaint.category_name}
                </span>
                {isFollowing && (
                  <span style={{ fontSize: "11px", fontWeight: "bold", backgroundColor: "#FEF3C7", color: "#92400E", padding: "2px 6px", borderRadius: "var(--radius-sm)" }}>
                    ★ Following
                  </span>
                )}
              </div>
              <CardTitle>{complaint.public_title}</CardTitle>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
              <StatusBadge status={complaint.status} />

              <Button
                variant={isFollowing ? "outline" : "primary"}
                size="sm"
                onClick={handleToggleFollow}
                isLoading={isFollowLoading}
                disabled={isFollowLoading}
              >
                {isFollowing ? "★ Following (Click to Unfollow)" : "☆ Follow Issue Updates"}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
            {/* Description */}
            <div>
              <h4 style={{ fontSize: "var(--text-sm)", fontWeight: "bold", color: "var(--color-text-main)", marginBottom: "var(--space-2)" }}>
                Verified Problem Description
              </h4>
              <p style={{ fontSize: "var(--text-base)", color: "var(--color-text-body)", lineHeight: "var(--leading-relaxed)", whiteSpace: "pre-line" }}>
                {complaint.public_description}
              </p>
            </div>

            {/* Public Attributes Grid */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: "var(--space-4)",
                padding: "var(--space-4)",
                backgroundColor: "var(--color-bg-app)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
              }}
            >
              <div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                  Issue Category
                </span>
                <span style={{ fontWeight: "600", color: "var(--color-text-main)", fontSize: "var(--text-sm)" }}>
                  {complaint.category_name}
                </span>
              </div>

              <div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                  Locality / District
                </span>
                <span style={{ fontWeight: "600", color: "var(--color-text-main)", fontSize: "var(--text-sm)" }}>
                  {locationDisplay}
                </span>
              </div>

              <div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                  Published Date
                </span>
                <span style={{ fontWeight: "600", color: "var(--color-text-main)", fontSize: "var(--text-sm)" }}>
                  {formatDate(complaint.created_at)}
                </span>
              </div>

              <div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                  Current Status
                </span>
                <span style={{ fontWeight: "600", color: "var(--color-text-main)", fontSize: "var(--text-sm)" }}>
                  {complaint.status}
                </span>
              </div>
            </div>

            {/* Privacy Protection Notice */}
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "var(--space-3)",
                padding: "var(--space-3) var(--space-4)",
                backgroundColor: "var(--color-bg-card)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <div style={{ color: "var(--color-primary)", marginTop: 2 }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", lineHeight: "var(--leading-relaxed)" }}>
                <strong style={{ color: "var(--color-text-main)" }}>Civic Transparency &amp; Privacy Protection:</strong>
                <br />
                To protect citizen confidentiality, all private addresses, exact geographic coordinates, personal contact numbers, and worker identity details are strictly redacted from public viewing.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Authentication Prompt Modal for Unauthenticated Follow Requests */}
      <ConfirmationDialog
        isOpen={isAuthModalOpen}
        title="Citizen Sign In Required"
        description="To follow community issues and receive status updates on this complaint, you need to sign in with your CivicPulse citizen account."
        confirmText="Proceed to Sign In"
        cancelText="Cancel"
        onConfirm={() => navigate("/login")}
        onCancel={() => setIsAuthModalOpen(false)}
      />
    </div>
  );
};
