import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import "./DashboardPages.css";
import { complaintService } from "../services/complaintService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { StatusBadge } from "../components/StatusBadge";
import { Alert } from "../components/Alert";
import { Spinner } from "../components/Spinner";
import { ComplaintStatusTracker } from "../components/ComplaintStatusTracker";
import { ComplaintTimeline } from "../components/ComplaintTimeline";
import { ConfirmationDialog } from "../components/ConfirmationDialog";

// Reopening grace period calculation (14 days from closed_at or resolved_at)
function checkReopeningEligibility(complaint) {
  if (!complaint) return false;
  if (complaint.status === "RESOLVED_AWAITING_VERIFICATION") return true;
  if (complaint.status === "CLOSED") {
    const refDateStr = complaint.closed_at || complaint.resolved_at;
    if (!refDateStr) return false;
    const refDate = new Date(refDateStr).getTime();
    return (Date.now() - refDate) <= 14 * 24 * 60 * 60 * 1000;
  }
  return false;
}

export const CitizenComplaintDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [complaint, setComplaint] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [history, setHistory] = useState([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("timeline");

  // Action Dialog States
  const [isCloseDialogOpen, setIsCloseDialogOpen] = useState(false);
  const [isReopenDialogOpen, setIsReopenDialogOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionFeedback, setActionFeedback] = useState(null);

  const fetchComplaintDetails = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const [compRes, timelineRes, historyRes] = await Promise.all([
        complaintService.getComplaint(id),
        complaintService.getComplaintTimeline(id).catch(() => null),
        complaintService.getComplaintHistory(id).catch(() => []),
      ]);

      setComplaint(compRes);
      setTimeline(timelineRes);
      setHistory(historyRes);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.statusCode === 403) {
          setError("Access Denied: You can only view complaints filed under your citizen account.");
        } else if (err.statusCode === 404) {
          setError("Complaint record not found. Please verify the complaint identifier.");
        } else {
          setError(err.message);
        }
      } else {
        setError("Unable to load complaint details. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchComplaintDetails();
  }, [fetchComplaintDetails]);

  // Handle Verify & Close
  const handleVerifyClose = async (reason) => {
    if (!id) return;
    setActionLoading(true);
    setActionFeedback(null);
    try {
      const updated = await complaintService.transitionStatus(id, {
        new_status: "CLOSED",
        remarks: reason || "Citizen verified and confirmed resolution on-site.",
      });
      setComplaint(updated);
      setIsCloseDialogOpen(false);
      setActionFeedback({
        type: "success",
        message: "Resolution verified! Complaint is now successfully closed.",
      });
      // Refresh timeline & history
      fetchComplaintDetails();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to verify complaint.";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Reopen
  const handleReopen = async (reason) => {
    if (!id) return;
    setActionLoading(true);
    setActionFeedback(null);
    try {
      const updated = await complaintService.transitionStatus(id, {
        new_status: "REOPENED",
        remarks: reason,
      });
      setComplaint(updated);
      setIsReopenDialogOpen(false);
      setActionFeedback({
        type: "success",
        message: "Complaint reopened. It has been returned to the municipal dispatch queue.",
      });
      // Refresh timeline & history
      fetchComplaintDetails();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to reopen complaint.";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "N/A";
    try {
      return new Date(dateStr).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const isEligibleForReopening = checkReopeningEligibility(complaint);

  if (isLoading && !complaint) {
    return (
      <div className="portal-page" style={{ alignItems: "center", justifyContent: "center", minHeight: "50vh" }}>
        <Spinner size="lg" />
        <span style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)" }}>
          Loading complaint dossier...
        </span>
      </div>
    );
  }

  if (error || !complaint) {
    return (
      <div className="portal-page">
        <Alert variant="error" title="Access Error">
          {error || "Unable to retrieve the requested complaint."}
        </Alert>
        <div style={{ marginTop: "var(--space-4)" }}>
          <Button variant="outline" onClick={() => navigate("/citizen/complaints")}>
            ← Back to My Complaints
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
            <Link to="/citizen/complaints" style={{ fontSize: "var(--text-sm)", color: "var(--color-primary)" }}>
              ← My Complaints
            </Link>
            <span style={{ color: "var(--color-text-muted)" }}>/</span>
            <span style={{ fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
              {complaint.complaint_number}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
            <h1 className="portal-header-title">{complaint.title}</h1>
            <StatusBadge status={complaint.status} />
          </div>
          <p className="portal-header-subtitle">
            Category: <strong>{complaint.category_name || `Category #${complaint.category_id}`}</strong> &bull; Filed on {formatDate(complaint.created_at)}
          </p>
        </div>

        <div className="portal-header-actions">
          <Button variant="outline" size="sm" onClick={fetchComplaintDetails}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            Refresh Timeline
          </Button>
        </div>
      </div>

      {actionFeedback && (
        <Alert variant={actionFeedback.type === "success" ? "success" : "error"}>
          {actionFeedback.message}
        </Alert>
      )}

      {/* Visual Stepper */}
      <Card>
        <CardContent>
          <ComplaintStatusTracker status={complaint.status} />
        </CardContent>
      </Card>

      {/* Action Required Banner for Citizens */}
      {complaint.status === "RESOLVED_AWAITING_VERIFICATION" && (
        <Card style={{ borderColor: "var(--color-secondary)", backgroundColor: "#F7FBFB" }}>
          <CardContent>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-4)" }}>
              <div>
                <h3 style={{ fontSize: "var(--text-base)", fontWeight: "var(--weight-bold)", color: "var(--color-primary)", marginBottom: "4px" }}>
                  Resolution Completed — Citizen Verification Required
                </h3>
                <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-body)", maxWidth: "560px" }}>
                  Field personnel reported this civic issue as resolved. Please review the completed on-site work and either confirm resolution or reopen the ticket.
                </p>
              </div>

              <div style={{ display: "flex", gap: "var(--space-3)" }}>
                <Button variant="outline" onClick={() => setIsReopenDialogOpen(true)}>
                  Reopen Issue
                </Button>
                <Button variant="primary" onClick={() => setIsCloseDialogOpen(true)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  Verify &amp; Close
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {complaint.status === "CLOSED" && isEligibleForReopening && (
        <Card style={{ backgroundColor: "var(--color-bg-subtle)" }}>
          <CardContent>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-4)" }}>
              <div>
                <h4 style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)" }}>
                  Verified Closed &bull; 14-Day Reopening Window Active
                </h4>
                <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "2px" }}>
                  If the problem has recurred or was not resolved adequately, you may reopen this complaint within 14 days of closure.
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => setIsReopenDialogOpen(true)}>
                Reopen Ticket
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Grid: Details + Timeline */}
      <div className="portal-grid-2col">
        {/* Left Column: Timeline & History Tabs */}
        <div>
          <Card>
            <CardHeader>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                <CardTitle>Milestone Audit Trail</CardTitle>
                <div style={{ display: "flex", gap: "var(--space-1)" }}>
                  <Button
                    size="sm"
                    variant={activeTab === "timeline" ? "primary" : "ghost"}
                    onClick={() => setActiveTab("timeline")}
                  >
                    Chronological Timeline
                  </Button>
                  <Button
                    size="sm"
                    variant={activeTab === "history" ? "primary" : "ghost"}
                    onClick={() => setActiveTab("history")}
                  >
                    Status History ({history.length})
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {activeTab === "timeline" ? (
                timeline?.events ? (
                  <ComplaintTimeline events={timeline.events} />
                ) : (
                  <p style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>No timeline events found.</p>
                )
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-xs)" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--color-border)", textAlign: "left" }}>
                        <th style={{ padding: "8px 12px", color: "var(--color-text-muted)" }}>Date</th>
                        <th style={{ padding: "8px 12px", color: "var(--color-text-muted)" }}>Transition</th>
                        <th style={{ padding: "8px 12px", color: "var(--color-text-muted)" }}>Authorized By</th>
                        <th style={{ padding: "8px 12px", color: "var(--color-text-muted)" }}>Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((h) => (
                        <tr key={h.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                          <td style={{ padding: "10px 12px", whiteSpace: "nowrap" }}>{formatDate(h.created_at)}</td>
                          <td style={{ padding: "10px 12px", whiteSpace: "nowrap" }}>
                            <span style={{ color: "var(--color-text-muted)" }}>{h.previous_status || "START"}</span>
                            <span style={{ margin: "0 4px" }}>→</span>
                            <strong>{h.new_status}</strong>
                          </td>
                          <td style={{ padding: "10px 12px" }}>{h.changed_by_name || "System"}</td>
                          <td style={{ padding: "10px 12px", color: "var(--color-text-body)" }}>{h.remarks || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Specification Dossier */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {/* Metadata Card */}
          <Card>
            <CardHeader>
              <CardTitle>Complaint Details</CardTitle>
            </CardHeader>
            <CardContent>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", fontSize: "var(--text-sm)" }}>
                <div>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                    Tracking Reference
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: "bold", color: "var(--color-primary)" }}>
                    {complaint.complaint_number}
                  </span>
                </div>

                <div>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                    Operational Priority
                  </span>
                  <span style={{ fontWeight: "bold" }}>{complaint.priority}</span>
                </div>

                <div>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                    Description
                  </span>
                  <p style={{ marginTop: "4px", color: "var(--color-text-body)", lineHeight: "var(--leading-relaxed)" }}>
                    {complaint.description}
                  </p>
                </div>

                <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
                    <div>
                      <span style={{ color: "var(--color-text-muted)", display: "block" }}>Submitted:</span>
                      <span>{formatDate(complaint.created_at)}</span>
                    </div>
                    <div>
                      <span style={{ color: "var(--color-text-muted)", display: "block" }}>Last Updated:</span>
                      <span>{formatDate(complaint.updated_at)}</span>
                    </div>
                    {complaint.resolved_at && (
                      <div>
                        <span style={{ color: "var(--color-text-muted)", display: "block" }}>Resolved:</span>
                        <span>{formatDate(complaint.resolved_at)}</span>
                      </div>
                    )}
                    {complaint.closed_at && (
                      <div>
                        <span style={{ color: "var(--color-text-muted)", display: "block" }}>Closed:</span>
                        <span>{formatDate(complaint.closed_at)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Location Card */}
          {complaint.location && (
            <Card>
              <CardHeader>
                <CardTitle>Location Coordinates</CardTitle>
              </CardHeader>
              <CardContent>
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", fontSize: "var(--text-sm)" }}>
                  {complaint.location.address_line && (
                    <div>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>Address</span>
                      <span>{complaint.location.address_line}</span>
                    </div>
                  )}

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
                    <div>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>Area / Ward</span>
                      <span>{complaint.location.area_name || "—"}</span>
                    </div>
                    <div>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>City</span>
                      <span>{complaint.location.city}</span>
                    </div>
                  </div>

                  {complaint.location.pincode && (
                    <div>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>Pincode</span>
                      <span>{complaint.location.pincode}</span>
                    </div>
                  )}

                  {complaint.location.landmark && (
                    <div>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>Landmark</span>
                      <span>{complaint.location.landmark}</span>
                    </div>
                  )}

                  <div style={{ backgroundColor: "var(--color-bg-app)", padding: "var(--space-2) var(--space-3)", borderRadius: "var(--radius-sm)", fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", marginTop: "var(--space-2)" }}>
                    Lat: {complaint.location.latitude.toFixed(6)}, Lng: {complaint.location.longitude.toFixed(6)}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Verify & Close Dialog */}
      <ConfirmationDialog
        isOpen={isCloseDialogOpen}
        title="Verify &amp; Close Complaint"
        description="Are you satisfied with the municipal resolution performed for this issue? Confirming will officially close the complaint."
        confirmText="Confirm Resolution &amp; Close"
        isLoading={actionLoading}
        onConfirm={handleVerifyClose}
        onCancel={() => setIsCloseDialogOpen(false)}
      />

      {/* Reopen Dialog */}
      <ConfirmationDialog
        isOpen={isReopenDialogOpen}
        title="Reopen Complaint"
        description="If the issue has not been fully resolved or has recurred, please explain what remains unaddressed. The ticket will return to municipal staff."
        confirmText="Submit Reopening Reason"
        variant="danger"
        requireReason
        reasonLabel="Mandatory Reopening Reason"
        reasonPlaceholder="Describe what was not resolved or why the problem persists..."
        isLoading={actionLoading}
        onConfirm={handleReopen}
        onCancel={() => setIsReopenDialogOpen(false)}
      />
    </div>
  );
};
