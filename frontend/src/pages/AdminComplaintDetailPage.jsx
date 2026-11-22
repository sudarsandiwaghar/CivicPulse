import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import "./DashboardPages.css";
import { adminService } from "../services/adminService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { StatusBadge } from "../components/StatusBadge";
import { ComplaintTimeline } from "../components/ComplaintTimeline";
import { AssignmentModal } from "../components/AssignmentModal";
import { TriageActionModal } from "../components/TriageActionModal";
import { PublicModerationModal } from "../components/PublicModerationModal";

function formatDate(dateStr) {
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
}

export const AdminComplaintDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [complaint, setComplaint] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [sla, setSla] = useState(null);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionFeedback, setActionFeedback] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Active view tab in main card
  const [activeTab, setActiveTab] = useState("timeline"); // "timeline" | "transitions" | "assignments"

  // Modals state
  const [isAssignmentModalOpen, setIsAssignmentModalOpen] = useState(false);
  const [assignmentMode, setAssignmentMode] = useState("assign");

  const [isTriageModalOpen, setIsTriageModalOpen] = useState(false);
  const [triageActionType, setTriageActionType] = useState("UNDER_REVIEW");

  const [isModerationModalOpen, setIsModerationModalOpen] = useState(false);
  const [moderationMode, setModerationMode] = useState("PUBLISH");

  const fetchComplaintDossier = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const [compRes, timelineRes, asgnRes, slaRes] = await Promise.all([
        adminService.getComplaint(id),
        adminService.getComplaintTimeline(id).catch(() => null),
        adminService.getComplaintAssignments(id).catch(() => ({ data: [] })),
        adminService.getComplaintSLA(id).catch(() => null),
      ]);

      setComplaint(compRes);
      setTimeline(timelineRes);
      setAssignments(asgnRes?.data || []);
      setSla(slaRes);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.statusCode === 404) {
          setError("Complaint record not found. Please verify the complaint identifier.");
        } else {
          setError(err.message);
        }
      } else {
        setError("Unable to load administrative complaint details. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchComplaintDossier();
  }, [fetchComplaintDossier]);

  // Handle direct review advance to UNDER_REVIEW
  const handleBeginReview = async () => {
    setActionLoading(true);
    setActionFeedback(null);
    try {
      await adminService.reviewComplaint(id, {
        new_status: "UNDER_REVIEW",
        reason: "Administrator initiated formal complaint review and verification.",
      });
      setActionFeedback({
        type: "success",
        message: "Complaint successfully transitioned to Under Review.",
      });
      await fetchComplaintDossier();
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: err.message || "Failed to update complaint status.",
      });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle triage action modal confirmation
  const handleTriageConfirm = async (payload) => {
    setActionLoading(true);
    setActionFeedback(null);
    try {
      await adminService.reviewComplaint(id, payload);
      setIsTriageModalOpen(false);
      setActionFeedback({
        type: "success",
        message: "Triage action applied successfully.",
      });
      await fetchComplaintDossier();
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: err.message || "Failed to apply triage action.",
      });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle assignment modal confirmation
  const handleAssignmentConfirm = async ({ workerId, reason, notes }) => {
    setActionLoading(true);
    setActionFeedback(null);
    try {
      if (assignmentMode === "assign") {
        await adminService.assignComplaint(id, {
          worker_id: workerId,
          notes: notes || null,
        });
        setActionFeedback({
          type: "success",
          message: "Field worker dispatched and assigned successfully.",
        });
      } else {
        await adminService.reassignComplaint(id, {
          new_worker_id: workerId,
          reason,
          notes: notes || null,
        });
        setActionFeedback({
          type: "success",
          message: "Complaint successfully reassigned to new field technician.",
        });
      }
      setIsAssignmentModalOpen(false);
      await fetchComplaintDossier();
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: err.message || "Failed to execute assignment operation.",
      });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle public moderation modal confirmation
  const handleModerationConfirm = async (payload) => {
    setActionLoading(true);
    setActionFeedback(null);
    try {
      await adminService.moderatePublic(id, payload);
      setIsModerationModalOpen(false);
      setActionFeedback({
        type: "success",
        message: `Public visibility updated: ${payload.action} completed.`,
      });
      await fetchComplaintDossier();
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: err.message || "Failed to update public moderation visibility.",
      });
    } finally {
      setActionLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="portal-page" style={{ padding: "4rem 0", textAlign: "center" }}>
        <Spinner size="lg" message="Loading administrative complaint dossier..." />
      </div>
    );
  }

  if (error || !complaint) {
    return (
      <div className="portal-page">
        <Alert variant="error">{error || "Complaint details unavailable."}</Alert>
        <div style={{ marginTop: "1rem" }}>
          <Button variant="secondary" onClick={() => navigate("/admin/complaints")}>
            &larr; Back to Complaints Queue
          </Button>
        </div>
      </div>
    );
  }

  const activeAssignment = assignments.find(
    (a) => a.status === "ASSIGNED" || a.status === "IN_PROGRESS"
  );

  const isAssignable = complaint.status === "UNDER_REVIEW";
  const isReassignable = complaint.status === "ASSIGNED" || complaint.status === "IN_PROGRESS";
  const isTriageable = !["CLOSED", "REJECTED", "DUPLICATE"].includes(complaint.status);

  return (
    <div className="portal-page">
      {/* Top Breadcrumb & Navigation */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
        <Link to="/admin" style={{ color: "var(--color-text-muted)", textDecoration: "none" }}>Admin</Link>
        <span>&rsaquo;</span>
        <Link to="/admin/complaints" style={{ color: "var(--color-text-muted)", textDecoration: "none" }}>Complaints</Link>
        <span>&rsaquo;</span>
        <span style={{ color: "var(--color-text-main)", fontWeight: "600" }}>{complaint.complaint_number}</span>
      </div>

      {actionFeedback && (
        <Alert
          variant={actionFeedback.type}
          dismissible
          onDismiss={() => setActionFeedback(null)}
        >
          {actionFeedback.message}
        </Alert>
      )}

      {/* Header with Title and Action Bar */}
      <div className="portal-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap", marginBottom: "0.5rem" }}>
            <h1 className="portal-header-title" style={{ margin: 0 }}>
              {complaint.complaint_number}
            </h1>
            <StatusBadge status={complaint.status} size="md" />
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: "700",
                textTransform: "uppercase",
                padding: "2px 8px",
                borderRadius: "var(--radius-sm)",
                backgroundColor:
                  complaint.priority === "URGENT"
                    ? "#fee2e2"
                    : complaint.priority === "HIGH"
                    ? "#fef3c7"
                    : "#f1f5f9",
                color:
                  complaint.priority === "URGENT"
                    ? "#991b1b"
                    : complaint.priority === "HIGH"
                    ? "#92400e"
                    : "#334155",
              }}
            >
              Priority: {complaint.priority}
            </span>
          </div>
          <p className="portal-header-subtitle">
            Filed on {formatDate(complaint.created_at)} &bull; Category: <strong>{complaint.category_name || "Uncategorized"}</strong>
          </p>
        </div>

        {/* Action Controls */}
        <div className="portal-header-actions" style={{ flexWrap: "wrap" }}>
          {complaint.status === "SUBMITTED" && (
            <Button
              variant="primary"
              onClick={handleBeginReview}
              disabled={actionLoading}
            >
              {actionLoading ? "Processing..." : "Start Review"}
            </Button>
          )}

          {isAssignable && (
            <Button
              variant="primary"
              onClick={() => {
                setAssignmentMode("assign");
                setIsAssignmentModalOpen(true);
              }}
              disabled={actionLoading}
            >
              Assign Field Worker
            </Button>
          )}

          {isReassignable && (
            <Button
              variant="secondary"
              onClick={() => {
                setAssignmentMode("reassign");
                setIsAssignmentModalOpen(true);
              }}
              disabled={actionLoading}
            >
              Reassign Worker
            </Button>
          )}

          {isTriageable && (
            <div style={{ display: "inline-flex", gap: "0.5rem" }}>
              <Button
                variant="outline"
                onClick={() => {
                  setTriageActionType("ADJUST_PRIORITY");
                  setIsTriageModalOpen(true);
                }}
              >
                Set Priority
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setTriageActionType("RECLASSIFY_CATEGORY");
                  setIsTriageModalOpen(true);
                }}
              >
                Reclassify
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  setTriageActionType("REJECTED");
                  setIsTriageModalOpen(true);
                }}
              >
                Reject
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Main 2-Column Content Layout */}
      <div className="portal-grid-2col">
        {/* Left Column: Dossier Details & Timeline/History */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
          {/* Specification Card */}
          <Card>
            <CardHeader>
              <CardTitle>Complaint Specification</CardTitle>
            </CardHeader>
            <CardContent>
              <div style={{ marginBottom: "1.25rem" }}>
                <h3 style={{ fontSize: "1.125rem", fontWeight: "600", color: "var(--color-text-main)", marginBottom: "0.5rem" }}>
                  {complaint.title}
                </h3>
                <p style={{ fontSize: "0.9375rem", lineHeight: "1.6", color: "var(--color-text-main)", whiteSpace: "pre-wrap" }}>
                  {complaint.description}
                </p>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: "1rem",
                  padding: "1rem",
                  backgroundColor: "var(--color-bg-app)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border-card)",
                }}
              >
                <div>
                  <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
                    Location / Ward
                  </span>
                  <p style={{ margin: "0.25rem 0 0", fontSize: "0.875rem", fontWeight: "500", color: "var(--color-text-main)" }}>
                    {complaint.location?.area_name || complaint.location?.city || "Location not recorded"}
                    {complaint.location?.address_line && ` (${complaint.location.address_line})`}
                  </p>
                </div>

                <div>
                  <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
                    City & Pincode
                  </span>
                  <p style={{ margin: "0.25rem 0 0", fontSize: "0.875rem", fontWeight: "500", color: "var(--color-text-main)" }}>
                    {complaint.location?.city} {complaint.location?.pincode ? `- ${complaint.location.pincode}` : ""}
                  </p>
                </div>

                <div>
                  <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
                    GPS Coordinates
                  </span>
                  <p style={{ margin: "0.25rem 0 0", fontSize: "0.875rem", fontWeight: "500", color: "var(--color-text-main)" }}>
                    {complaint.location?.latitude && complaint.location?.longitude ? (
                      <a
                        href={`https://maps.google.com/?q=${complaint.location.latitude},${complaint.location.longitude}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: "var(--color-primary)", textDecoration: "underline" }}
                      >
                        {complaint.location.latitude.toFixed(4)}, {complaint.location.longitude.toFixed(4)}
                      </a>
                    ) : (
                      "Not available"
                    )}
                  </p>
                </div>

                <div>
                  <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
                    Last Updated
                  </span>
                  <p style={{ margin: "0.25rem 0 0", fontSize: "0.875rem", fontWeight: "500", color: "var(--color-text-main)" }}>
                    {formatDate(complaint.updated_at)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Activity, Timeline & Assignments Tabbed Card */}
          <Card>
            <div
              style={{
                display: "flex",
                borderBottom: "1px solid var(--color-border-card)",
                padding: "0 1.25rem",
                gap: "1.5rem",
              }}
            >
              <button
                onClick={() => setActiveTab("timeline")}
                style={{
                  padding: "1rem 0",
                  background: "none",
                  border: "none",
                  borderBottom: activeTab === "timeline" ? "2px solid var(--color-primary)" : "2px solid transparent",
                  color: activeTab === "timeline" ? "var(--color-primary)" : "var(--color-text-muted)",
                  fontWeight: activeTab === "timeline" ? "600" : "500",
                  fontSize: "0.875rem",
                  cursor: "pointer",
                }}
              >
                Chronological Timeline ({timeline?.events?.length || 0})
              </button>

              <button
                onClick={() => setActiveTab("transitions")}
                style={{
                  padding: "1rem 0",
                  background: "none",
                  border: "none",
                  borderBottom: activeTab === "transitions" ? "2px solid var(--color-primary)" : "2px solid transparent",
                  color: activeTab === "transitions" ? "var(--color-primary)" : "var(--color-text-muted)",
                  fontWeight: activeTab === "transitions" ? "600" : "500",
                  fontSize: "0.875rem",
                  cursor: "pointer",
                }}
              >
                Status Transitions ({complaint.status_history?.length || 0})
              </button>

              <button
                onClick={() => setActiveTab("assignments")}
                style={{
                  padding: "1rem 0",
                  background: "none",
                  border: "none",
                  borderBottom: activeTab === "assignments" ? "2px solid var(--color-primary)" : "2px solid transparent",
                  color: activeTab === "assignments" ? "var(--color-primary)" : "var(--color-text-muted)",
                  fontWeight: activeTab === "assignments" ? "600" : "500",
                  fontSize: "0.875rem",
                  cursor: "pointer",
                }}
              >
                Field Assignments ({assignments.length})
              </button>
            </div>

            <CardContent>
              {activeTab === "timeline" && (
                <ComplaintTimeline events={timeline?.events || []} />
              )}

              {activeTab === "transitions" && (
                <div>
                  {complaint.status_history && complaint.status_history.length > 0 ? (
                    <div style={{ overflowX: "auto" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                        <thead>
                          <tr style={{ borderBottom: "1px solid var(--color-border-card)", textAlign: "left", color: "var(--color-text-muted)" }}>
                            <th style={{ padding: "0.75rem" }}>Date & Time</th>
                            <th style={{ padding: "0.75rem" }}>From &rarr; To</th>
                            <th style={{ padding: "0.75rem" }}>Changed By</th>
                            <th style={{ padding: "0.75rem" }}>Remarks / Justification</th>
                          </tr>
                        </thead>
                        <tbody>
                          {complaint.status_history.map((h) => (
                            <tr key={h.id} style={{ borderBottom: "1px solid var(--color-border-card)" }}>
                              <td style={{ padding: "0.75rem", whiteSpace: "nowrap" }}>{formatDate(h.created_at)}</td>
                              <td style={{ padding: "0.75rem" }}>
                                <span style={{ fontWeight: "600" }}>{h.previous_status || "INITIAL"}</span>
                                &nbsp;&rarr;&nbsp;
                                <span style={{ color: "var(--color-primary)", fontWeight: "600" }}>{h.new_status}</span>
                              </td>
                              <td style={{ padding: "0.75rem" }}>{h.changed_by_name || "System / Admin"}</td>
                              <td style={{ padding: "0.75rem", color: "var(--color-text-muted)" }}>{h.remarks || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p style={{ color: "var(--color-text-muted)", textAlign: "center", padding: "1.5rem 0" }}>
                      No prior status transition records recorded.
                    </p>
                  )}
                </div>
              )}

              {activeTab === "assignments" && (
                <div>
                  {assignments.length > 0 ? (
                    <div style={{ overflowX: "auto" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                        <thead>
                          <tr style={{ borderBottom: "1px solid var(--color-border-card)", textAlign: "left", color: "var(--color-text-muted)" }}>
                            <th style={{ padding: "0.75rem" }}>Technician</th>
                            <th style={{ padding: "0.75rem" }}>Department</th>
                            <th style={{ padding: "0.75rem" }}>Status</th>
                            <th style={{ padding: "0.75rem" }}>Assigned At</th>
                            <th style={{ padding: "0.75rem" }}>Completed At</th>
                            <th style={{ padding: "0.75rem" }}>Dispatch Notes</th>
                          </tr>
                        </thead>
                        <tbody>
                          {assignments.map((asgn) => (
                            <tr key={asgn.id} style={{ borderBottom: "1px solid var(--color-border-card)" }}>
                              <td style={{ padding: "0.75rem", fontWeight: "600" }}>
                                {asgn.worker_name || "Field Worker"}
                                {asgn.worker_employee_id && (
                                  <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", fontWeight: "normal" }}>
                                    ID: {asgn.worker_employee_id}
                                  </div>
                                )}
                              </td>
                              <td style={{ padding: "0.75rem" }}>{asgn.department_name || "Municipal Service"}</td>
                              <td style={{ padding: "0.75rem" }}>
                                <span
                                  style={{
                                    fontSize: "0.75rem",
                                    padding: "2px 8px",
                                    borderRadius: "var(--radius-sm)",
                                    fontWeight: "600",
                                    backgroundColor:
                                      asgn.status === "COMPLETED"
                                        ? "#dcfce7"
                                        : asgn.status === "IN_PROGRESS"
                                        ? "#dbeafe"
                                        : asgn.status === "REASSIGNED"
                                        ? "#fef3c7"
                                        : "#f1f5f9",
                                    color:
                                      asgn.status === "COMPLETED"
                                        ? "#15803d"
                                        : asgn.status === "IN_PROGRESS"
                                        ? "#1d4ed8"
                                        : asgn.status === "REASSIGNED"
                                        ? "#b45309"
                                        : "#475569",
                                  }}
                                >
                                  {asgn.status}
                                </span>
                              </td>
                              <td style={{ padding: "0.75rem", whiteSpace: "nowrap" }}>{formatDate(asgn.assigned_at)}</td>
                              <td style={{ padding: "0.75rem", whiteSpace: "nowrap" }}>{formatDate(asgn.completed_at)}</td>
                              <td style={{ padding: "0.75rem", color: "var(--color-text-muted)" }}>{asgn.notes || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p style={{ color: "var(--color-text-muted)", textAlign: "center", padding: "1.5rem 0" }}>
                      No field technicians have been assigned to this complaint yet.
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Operational Cards (SLA, Reporting Citizen, Public Visibility, Workforce) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
          {/* Dual-Clock SLA Performance Card */}
          <Card>
            <CardHeader>
              <CardTitle>Dual-Clock SLA Performance</CardTitle>
            </CardHeader>
            <CardContent>
              {sla ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {/* Response Clock */}
                  <div
                    style={{
                      padding: "0.75rem 1rem",
                      borderRadius: "var(--radius-md)",
                      backgroundColor: sla.response_breached ? "#fef2f2" : "#f0fdf4",
                      border: `1px solid ${sla.response_breached ? "#fca5a5" : "#bbf7d0"}`,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "0.8125rem", fontWeight: "700", textTransform: "uppercase" }}>
                        Response SLA Clock
                      </span>
                      <span
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: "700",
                          color: sla.response_breached ? "#b91c1c" : "#15803d",
                        }}
                      >
                        {sla.response_breached ? "BREACHED" : sla.responded_at ? "MET" : "ON TRACK"}
                      </span>
                    </div>
                    <div style={{ marginTop: "0.5rem", fontSize: "0.8125rem", color: "var(--color-text-main)" }}>
                      <div>Deadline: <strong>{formatDate(sla.response_deadline)}</strong></div>
                      {sla.responded_at && <div>Responded: {formatDate(sla.responded_at)}</div>}
                      {sla.response_escalation_level > 0 && (
                        <div style={{ color: "#b91c1c", fontWeight: "600", marginTop: "2px" }}>
                          Escalation Level: {sla.response_escalation_level}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Resolution Clock */}
                  <div
                    style={{
                      padding: "0.75rem 1rem",
                      borderRadius: "var(--radius-md)",
                      backgroundColor: sla.resolution_breached ? "#fef2f2" : "#f0fdf4",
                      border: `1px solid ${sla.resolution_breached ? "#fca5a5" : "#bbf7d0"}`,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "0.8125rem", fontWeight: "700", textTransform: "uppercase" }}>
                        Resolution SLA Clock
                      </span>
                      <span
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: "700",
                          color: sla.resolution_breached ? "#b91c1c" : "#15803d",
                        }}
                      >
                        {sla.resolution_breached ? "BREACHED" : sla.resolved_at ? "MET" : "ACTIVE"}
                      </span>
                    </div>
                    <div style={{ marginTop: "0.5rem", fontSize: "0.8125rem", color: "var(--color-text-main)" }}>
                      <div>Deadline: <strong>{formatDate(sla.resolution_deadline)}</strong></div>
                      {sla.resolved_at && <div>Resolved: {formatDate(sla.resolved_at)}</div>}
                      {sla.resolution_escalation_level > 0 && (
                        <div style={{ color: "#b91c1c", fontWeight: "600", marginTop: "2px" }}>
                          Escalation Level: {sla.resolution_escalation_level}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)", margin: 0 }}>
                  Standard SLA metrics are calculated based on category SLA policy.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Reporting Citizen Card */}
          <Card>
            <CardHeader>
              <CardTitle>Reporting Citizen</CardTitle>
            </CardHeader>
            <CardContent>
              <div style={{ fontSize: "0.875rem", lineHeight: "1.6" }}>
                <div>
                  <span style={{ color: "var(--color-text-muted)" }}>Name: </span>
                  <strong>{complaint.citizen_name || "Anonymous Citizen"}</strong>
                </div>
                <div>
                  <span style={{ color: "var(--color-text-muted)" }}>Citizen ID: </span>
                  <code style={{ fontSize: "0.75rem" }}>{complaint.citizen_id}</code>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Public Moderation Card */}
          <Card>
            <CardHeader>
              <CardTitle>Public Feed Moderation</CardTitle>
            </CardHeader>
            <CardContent>
              <div style={{ fontSize: "0.875rem", marginBottom: "1rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <span style={{ color: "var(--color-text-muted)" }}>Visibility:</span>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      fontWeight: "700",
                      padding: "2px 8px",
                      borderRadius: "var(--radius-sm)",
                      backgroundColor: complaint.is_public ? "#dcfce7" : "#f1f5f9",
                      color: complaint.is_public ? "#15803d" : "#475569",
                    }}
                  >
                    {complaint.is_public ? "PUBLISHED (PUBLIC)" : "UNLISTED (INTERNAL)"}
                  </span>
                </div>
                {complaint.is_public && complaint.public_title && (
                  <div style={{ marginTop: "0.5rem", padding: "0.5rem", backgroundColor: "var(--color-bg-app)", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ fontWeight: "600", fontSize: "0.8125rem" }}>{complaint.public_title}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: "2px" }}>
                      {complaint.public_description}
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {!complaint.is_public ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setModerationMode("PUBLISH");
                      setIsModerationModalOpen(true);
                    }}
                  >
                    Publish to Feed
                  </Button>
                ) : (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setModerationMode("UPDATE");
                        setIsModerationModalOpen(true);
                      }}
                    >
                      Edit Public Copy
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        setModerationMode("REVOKE");
                        setIsModerationModalOpen(true);
                      }}
                    >
                      Revoke Publication
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Active Field Assignment Card */}
          {activeAssignment && (
            <Card>
              <CardHeader>
                <CardTitle>Assigned Field Technician</CardTitle>
              </CardHeader>
              <CardContent>
                <div style={{ fontSize: "0.875rem", lineHeight: "1.6" }}>
                  <div>
                    <span style={{ color: "var(--color-text-muted)" }}>Worker: </span>
                    <strong>{activeAssignment.worker_name}</strong>
                  </div>
                  <div>
                    <span style={{ color: "var(--color-text-muted)" }}>Employee ID: </span>
                    <span>{activeAssignment.worker_employee_id || "—"}</span>
                  </div>
                  <div>
                    <span style={{ color: "var(--color-text-muted)" }}>Department: </span>
                    <span>{activeAssignment.department_name}</span>
                  </div>
                  <div>
                    <span style={{ color: "var(--color-text-muted)" }}>Current Status: </span>
                    <span style={{ fontWeight: "600", color: "var(--color-primary)" }}>{activeAssignment.status}</span>
                  </div>
                  <div>
                    <span style={{ color: "var(--color-text-muted)" }}>Assigned: </span>
                    <span>{formatDate(activeAssignment.assigned_at)}</span>
                  </div>
                  {activeAssignment.notes && (
                    <div style={{ marginTop: "0.5rem", padding: "0.5rem", backgroundColor: "var(--color-bg-app)", borderRadius: "var(--radius-sm)" }}>
                      <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Notes: </span>
                      <span>{activeAssignment.notes}</span>
                    </div>
                  )}
                </div>

                <div style={{ marginTop: "1rem" }}>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setAssignmentMode("reassign");
                      setIsAssignmentModalOpen(true);
                    }}
                  >
                    Reassign To Other Worker
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Assignment Modal */}
      <AssignmentModal
        isOpen={isAssignmentModalOpen}
        mode={assignmentMode}
        complaint={complaint}
        currentWorkerId={activeAssignment?.worker_id}
        isLoading={actionLoading}
        onConfirm={handleAssignmentConfirm}
        onCancel={() => setIsAssignmentModalOpen(false)}
      />

      {/* Triage Action Modal */}
      <TriageActionModal
        isOpen={isTriageModalOpen}
        actionType={triageActionType}
        complaint={complaint}
        isLoading={actionLoading}
        onConfirm={handleTriageConfirm}
        onCancel={() => setIsTriageModalOpen(false)}
      />

      {/* Public Moderation Modal */}
      <PublicModerationModal
        isOpen={isModerationModalOpen}
        mode={moderationMode}
        complaint={complaint}
        isLoading={actionLoading}
        onConfirm={handleModerationConfirm}
        onCancel={() => setIsModerationModalOpen(false)}
      />
    </div>
  );
};

export default AdminComplaintDetailPage;
