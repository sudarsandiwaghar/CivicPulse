import React, { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import "./DashboardPages.css";
import { workerService } from "../services/workerService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { StatusBadge } from "../components/StatusBadge";
import { Alert } from "../components/Alert";
import { Spinner } from "../components/Spinner";
import { ConfirmationDialog } from "../components/ConfirmationDialog";
import { ComplaintMap } from "../components/maps/ComplaintMap";
import { isValidCoordinate } from "../components/maps/ComplaintMapMarker";

function formatDateTime(dateStr) {
  if (!dateStr) return null;
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

export const WorkerTaskDetailPage = () => {
  const { assignmentId } = useParams();

  const [task, setTask] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionFeedback, setActionFeedback] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Action Modals State
  const [isAcceptOpen, setIsAcceptOpen] = useState(false);
  const [isStartOpen, setIsStartOpen] = useState(false);
  const [isProgressOpen, setIsProgressOpen] = useState(false);
  const [isCompleteOpen, setIsCompleteOpen] = useState(false);

  // Form Fields
  const [progressDesc, setProgressDesc] = useState("");
  const [progressError, setProgressError] = useState(null);

  const [completionSummary, setCompletionSummary] = useState("");
  const [completionError, setCompletionError] = useState(null);

  const fetchTaskDetails = useCallback(async () => {
    if (!assignmentId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await workerService.getTaskDetail(assignmentId);
      setTask(data);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.statusCode === 403) {
          setError(
            "Access Denied: You are not authorized to view this work order. Tasks are strictly scoped to designated technicians."
          );
        } else if (err.statusCode === 404) {
          setError("Work order assignment not found. It may have been reassigned or deleted.");
        } else {
          setError(err.message || "Failed to load task details.");
        }
      } else {
        setError("Network error. Please verify your connection.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [assignmentId]);

  useEffect(() => {
    fetchTaskDetails();
  }, [fetchTaskDetails]);

  // Action 1: Accept Assignment
  const handleAccept = async () => {
    setActionLoading(true);
    setActionFeedback(null);
    try {
      const updated = await workerService.acceptTask(assignmentId);
      setTask(updated);
      setIsAcceptOpen(false);
      setActionFeedback({
        type: "success",
        message: "Work order accepted successfully. You have acknowledged receipt.",
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to accept task.";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Action 2: Start Work
  const handleStart = async (notes) => {
    setActionLoading(true);
    setActionFeedback(null);
    try {
      const updated = await workerService.startTask(assignmentId, notes);
      setTask(updated);
      setIsStartOpen(false);
      setActionFeedback({
        type: "success",
        message: "Work initiated. Task and complaint are now In Progress.",
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to start work.";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setActionLoading(false);
    }
  };

  // Action 3: Log Progress Milestone
  const handleProgressSubmit = async (e) => {
    e.preventDefault();
    const cleaned = progressDesc.trim();
    if (cleaned.length < 5) {
      setProgressError("Progress description must contain at least 5 characters.");
      return;
    }
    if (cleaned.length > 2000) {
      setProgressError("Progress description cannot exceed 2000 characters.");
      return;
    }

    setActionLoading(true);
    setProgressError(null);
    setActionFeedback(null);
    try {
      await workerService.logProgress(assignmentId, cleaned);
      setIsProgressOpen(false);
      setProgressDesc("");
      setActionFeedback({
        type: "success",
        message: "Progress update logged to audit history.",
      });
      await fetchTaskDetails();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to log progress.";
      setProgressError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  // Action 4: Complete Task
  const handleCompleteSubmit = async (e) => {
    e.preventDefault();
    const cleaned = completionSummary.trim();
    if (cleaned.length < 10) {
      setCompletionError("Remediation summary must contain at least 10 characters.");
      return;
    }
    if (cleaned.length > 2000) {
      setCompletionError("Remediation summary cannot exceed 2000 characters.");
      return;
    }

    setActionLoading(true);
    setCompletionError(null);
    setActionFeedback(null);
    try {
      const updated = await workerService.completeTask(assignmentId, cleaned);
      setTask(updated);
      setIsCompleteOpen(false);
      setCompletionSummary("");
      setActionFeedback({
        type: "success",
        message: "Work order completed and submitted for citizen verification.",
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to complete task.";
      setCompletionError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  if (isLoading && !task) {
    return (
      <div
        className="portal-page"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "50vh",
        }}
      >
        <Spinner size="lg" />
        <span style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)" }}>
          Loading work order dossier...
        </span>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="portal-page">
        <Alert variant="error" title="Access Error">
          {error || "Unable to retrieve the requested work order."}
        </Alert>
        <div style={{ marginTop: "var(--space-4)" }}>
          <Link to="/worker/tasks">
            <Button variant="secondary">&larr; Return to Task Queue</Button>
          </Link>
        </div>
      </div>
    );
  }

  const isPendingAcceptance =
    task.assignment_status === "ASSIGNED" && !task.accepted_at;
  const isAcceptedPendingStart =
    task.assignment_status === "ASSIGNED" && Boolean(task.accepted_at);
  const isInProgress = task.assignment_status === "IN_PROGRESS";
  const isCompleted = task.assignment_status === "COMPLETED";

  const priorityClass = `priority-${(task.priority || "medium").toLowerCase()}`;

  // Reverse chronological progress updates
  const progressList = Array.isArray(task.progress_history)
    ? [...task.progress_history].sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at)
      )
    : [];

  return (
    <div className="portal-page">
      {/* Top Breadcrumb & Navigation */}
      <div style={{ marginBottom: "var(--space-3)" }}>
        <Link
          to="/worker/tasks"
          style={{
            fontSize: "var(--text-sm)",
            fontWeight: "var(--weight-bold)",
            color: "var(--color-primary)",
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: "var(--space-1)",
          }}
        >
          &larr; Back to Assigned Tasks
        </Link>
      </div>

      {/* Dossier Header */}
      <div className="portal-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontWeight: "bold",
                color: "var(--color-primary)",
                backgroundColor: "var(--color-bg-active-nav)",
                padding: "4px 10px",
                borderRadius: "var(--radius-sm)",
                fontSize: "var(--text-sm)",
              }}
            >
              {task.complaint_number}
            </span>
            {task.category_name && (
              <span
                style={{
                  fontSize: "var(--text-xs)",
                  padding: "4px 8px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: "var(--color-bg-subtle)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-muted)",
                }}
              >
                {task.category_name}
              </span>
            )}
            {task.priority && (
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: "bold",
                  padding: "3px 8px",
                  borderRadius: "var(--radius-sm)",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
                className={priorityClass}
              >
                {task.priority} Priority
              </span>
            )}
            <StatusBadge status={task.complaint_status} />
          </div>

          <h1 className="portal-header-title" style={{ marginTop: "var(--space-2)" }}>
            {task.title}
          </h1>
        </div>

        {/* Operational Stage Badge */}
        <div>
          {isPendingAcceptance && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                backgroundColor: "#fffbeb",
                color: "#b45309",
                border: "1px solid #fde68a",
                padding: "6px 14px",
                borderRadius: "var(--radius-full)",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--weight-semibold)",
              }}
            >
              <span>●</span> Awaiting Acceptance
            </span>
          )}
          {isAcceptedPendingStart && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                backgroundColor: "#e6f7f8",
                color: "#087f8c",
                border: "1px solid #bce7eb",
                padding: "6px 14px",
                borderRadius: "var(--radius-full)",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--weight-semibold)",
              }}
            >
              <span>✓</span> Accepted (Ready to Start)
            </span>
          )}
          {isInProgress && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                backgroundColor: "#f0f9ff",
                color: "#0369a1",
                border: "1px solid #bae6fd",
                padding: "6px 14px",
                borderRadius: "var(--radius-full)",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--weight-semibold)",
              }}
            >
              <span>⚙</span> Work In Progress
            </span>
          )}
          {isCompleted && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                backgroundColor: "#ecfdf5",
                color: "#047857",
                border: "1px solid #a7f3d0",
                padding: "6px 14px",
                borderRadius: "var(--radius-full)",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--weight-semibold)",
              }}
            >
              <span>★</span> Completed
            </span>
          )}
        </div>
      </div>

      {/* Global Feedback Banner */}
      {actionFeedback && (
        <Alert
          variant={actionFeedback.type}
          title={actionFeedback.type === "success" ? "Success" : "Notification"}
          onClose={() => setActionFeedback(null)}
        >
          {actionFeedback.message}
        </Alert>
      )}

      {/* 2-Column Responsive Dossier Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1.1fr)",
          gap: "var(--space-6)",
          alignItems: "start",
        }}
      >
        {/* Main Left Column: Issue, Location, Progress History */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
          {/* Problem Description Card */}
          <Card>
            <CardHeader>
              <CardTitle>Complaint Details</CardTitle>
            </CardHeader>
            <CardContent>
              <p
                style={{
                  fontSize: "var(--text-base)",
                  color: "var(--color-text-main)",
                  lineHeight: 1.6,
                  margin: 0,
                  whiteSpace: "pre-line",
                }}
              >
                {task.description || "No detailed description provided."}
              </p>

              {task.notes && (
                <div
                  style={{
                    marginTop: "var(--space-4)",
                    padding: "var(--space-3) var(--space-4)",
                    backgroundColor: "var(--color-bg-subtle)",
                    borderLeft: "4px solid var(--color-primary)",
                    borderRadius: "0 var(--radius-sm) var(--radius-sm) 0",
                  }}
                >
                  <span
                    style={{
                      fontSize: "var(--text-xs)",
                      fontWeight: "bold",
                      color: "var(--color-tertiary)",
                      textTransform: "uppercase",
                      display: "block",
                      marginBottom: "4px",
                    }}
                  >
                    Administrator Dispatch Instructions:
                  </span>
                  <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-body)" }}>
                    {task.notes}
                  </span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Incident Location Card */}
          <Card>
            <CardHeader>
              <CardTitle>Incident Location & Field Access</CardTitle>
            </CardHeader>
            <CardContent>
              {task.location ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
                    <div>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                        Street Address
                      </span>
                      <strong style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                        {task.location.address_line1 || "Street on file"}
                        {task.location.address_line2 ? `, ${task.location.address_line2}` : ""}
                      </strong>
                    </div>

                    <div>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                        Landmark / Sector
                      </span>
                      <strong style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                        {task.location.landmark || "N/A"}
                      </strong>
                    </div>

                    <div>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                        Ward / District
                      </span>
                      <strong style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                        {task.location.ward_or_district || "N/A"}
                      </strong>
                    </div>

                    <div>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                        City & State
                      </span>
                      <strong style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                        {task.location.city}, {task.location.state || ""} {task.location.pincode || ""}
                      </strong>
                    </div>
                  </div>

                  {/* Embedded Leaflet Map for Technician Field Navigation */}
                  {task.location && isValidCoordinate(task.location.latitude, task.location.longitude) && (
                    <div style={{ marginTop: "var(--space-2)" }}>
                      <ComplaintMap
                        complaints={[
                          {
                            id: task.complaint_id || task.id,
                            complaint_number: task.complaint_number,
                            title: task.title,
                            status: task.status,
                            priority: task.priority,
                            location: {
                              latitude: task.location.latitude,
                              longitude: task.location.longitude,
                              area_name: task.location.area_name || task.location.ward_or_district,
                              city: task.location.city,
                              address_line: task.location.address_line || task.location.address_line1,
                            },
                          },
                        ]}
                        center={[task.location.latitude, task.location.longitude]}
                        zoom={15}
                        height="260px"
                        showLegend={false}
                        userRole="FIELD_WORKER"
                      />
                    </div>
                  )}

                  {/* Coordinates & Navigation Link */}
                  {(task.location.latitude != null && task.location.longitude != null) && (
                    <div
                      style={{
                        marginTop: "var(--space-2)",
                        paddingTop: "var(--space-3)",
                        borderTop: "1px solid var(--color-border)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        flexWrap: "wrap",
                        gap: "var(--space-2)",
                      }}
                    >
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                        GPS Coordinates:{" "}
                        <strong style={{ fontFamily: "var(--font-mono)" }}>
                          {task.location.latitude.toFixed(6)}, {task.location.longitude.toFixed(6)}
                        </strong>
                      </span>

                      <a
                        href={`https://maps.google.com/?q=${task.location.latitude},${task.location.longitude}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          fontSize: "var(--text-xs)",
                          fontWeight: "bold",
                          color: "var(--color-primary)",
                          textDecoration: "none",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polygon points="3 11 22 2 13 21 11 13 3 11" />
                        </svg>
                        Open in Navigation App &rarr;
                      </a>
                    </div>
                  )}
                </div>
              ) : (
                <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
                  Standard municipal area sector.
                </span>
              )}
            </CardContent>
          </Card>

          {/* Progress Audit Trail */}
          <Card>
            <CardHeader>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
                <CardTitle>Milestone Progress History</CardTitle>
                {isInProgress && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setProgressError(null);
                      setProgressDesc("");
                      setIsProgressOpen(true);
                    }}
                  >
                    + Add Progress Note
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {progressList.length === 0 ? (
                <div style={{ textAlign: "center", padding: "var(--space-4)", color: "var(--color-text-muted)" }}>
                  <span>No intermediate progress updates logged yet.</span>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                  {progressList.map((p, idx) => (
                    <div
                      key={p.id || idx}
                      style={{
                        padding: "var(--space-3)",
                        backgroundColor: "var(--color-bg-subtle)",
                        borderRadius: "var(--radius-sm)",
                        borderLeft: "3px solid var(--color-secondary)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: "var(--space-1)",
                        }}
                      >
                        <strong style={{ fontSize: "var(--text-xs)", color: "var(--color-tertiary)" }}>
                          {p.worker_name || "Assigned Technician"}
                        </strong>
                        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                          {formatDateTime(p.created_at)}
                        </span>
                      </div>
                      <p
                        style={{
                          fontSize: "var(--text-sm)",
                          color: "var(--color-text-main)",
                          margin: 0,
                          lineHeight: 1.5,
                        }}
                      >
                        {p.description}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Sidebar: Operational Actions & Metadata */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
          {/* Action Card */}
          <Card>
            <CardHeader>
              <CardTitle>Workflow Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {/* Stage 1: Pending Acceptance */}
                {isPendingAcceptance && (
                  <>
                    <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", margin: 0 }}>
                      This complaint has been assigned to your unit. Please acknowledge receipt to proceed.
                    </p>
                    <Button
                      variant="primary"
                      disabled={actionLoading}
                      onClick={() => setIsAcceptOpen(true)}
                    >
                      Accept Assignment
                    </Button>
                    <Button
                      variant="outline"
                      disabled={actionLoading}
                      onClick={() => setIsStartOpen(true)}
                    >
                      Start Work Directly
                    </Button>
                  </>
                )}

                {/* Stage 2: Accepted, Ready to Start */}
                {isAcceptedPendingStart && (
                  <>
                    <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", margin: 0 }}>
                      Work order acknowledged. Initiate work on site when you arrive at the incident location.
                    </p>
                    <Button
                      variant="primary"
                      disabled={actionLoading}
                      onClick={() => setIsStartOpen(true)}
                    >
                      Start Work On Site
                    </Button>
                  </>
                )}

                {/* Stage 3: In Progress */}
                {isInProgress && (
                  <>
                    <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", margin: 0 }}>
                      Work is underway. Submit intermediate milestones or complete the resolution once finished.
                    </p>
                    <Button
                      variant="primary"
                      disabled={actionLoading}
                      onClick={() => {
                        setCompletionError(null);
                        setCompletionSummary("");
                        setIsCompleteOpen(true);
                      }}
                    >
                      Complete Work Order
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={actionLoading}
                      onClick={() => {
                        setProgressError(null);
                        setProgressDesc("");
                        setIsProgressOpen(true);
                      }}
                    >
                      Log Progress Milestone
                    </Button>
                  </>
                )}

                {/* Stage 4: Completed */}
                {isCompleted && (
                  <div
                    style={{
                      padding: "var(--space-3)",
                      backgroundColor: "#ecfdf5",
                      border: "1px solid #a7f3d0",
                      borderRadius: "var(--radius-sm)",
                    }}
                  >
                    <strong style={{ fontSize: "var(--text-sm)", color: "#047857", display: "block" }}>
                      Work Order Completed
                    </strong>
                    <span style={{ fontSize: "var(--text-xs)", color: "#065f46", marginTop: 4, display: "block" }}>
                      Remediation finished. Complaint has moved to <em>RESOLVED_AWAITING_VERIFICATION</em> for reporting citizen review.
                    </span>
                  </div>
                )}

                {/* Stage 5: Reassigned */}
                {task.assignment_status === "REASSIGNED" && (
                  <div
                    style={{
                      padding: "var(--space-3)",
                      backgroundColor: "#f3f4f6",
                      border: "1px solid #e5e7eb",
                      borderRadius: "var(--radius-sm)",
                    }}
                  >
                    <strong style={{ fontSize: "var(--text-sm)", color: "#374151", display: "block" }}>
                      Assignment Superseded
                    </strong>
                    <span style={{ fontSize: "var(--text-xs)", color: "#4b5563", marginTop: 4, display: "block" }}>
                      This task was reassigned to another technician.
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Assignment Metadata Card */}
          <Card>
            <CardHeader>
              <CardTitle>Work Order Metadata</CardTitle>
            </CardHeader>
            <CardContent>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                <div>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                    Reporting Citizen
                  </span>
                  <strong style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                    {task.citizen_name || "Confidential / Protected"}
                  </strong>
                </div>

                <div>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                    Assigned Date & Time
                  </span>
                  <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                    {formatDateTime(task.assigned_at) || "N/A"}
                  </span>
                </div>

                <div>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                    Accepted Date & Time
                  </span>
                  <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                    {formatDateTime(task.accepted_at) || "Pending"}
                  </span>
                </div>

                <div>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                    Work Started
                  </span>
                  <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                    {formatDateTime(task.started_at) || "Not started"}
                  </span>
                </div>

                {task.completed_at && (
                  <div>
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                      Work Completed
                    </span>
                    <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                      {formatDateTime(task.completed_at)}
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Confirmation Dialog: Accept Assignment */}
      <ConfirmationDialog
        isOpen={isAcceptOpen}
        title="Accept Work Order Assignment"
        description="Acknowledge receipt of this assigned civic complaint. The administrator and reporting citizen will receive an operational receipt confirmation."
        confirmText="Confirm Acceptance"
        variant="primary"
        isLoading={actionLoading}
        onConfirm={handleAccept}
        onCancel={() => setIsAcceptOpen(false)}
      />

      {/* Confirmation Dialog: Start Work */}
      <ConfirmationDialog
        isOpen={isStartOpen}
        title="Initiate Work On Site"
        description="Starting work transitions the assignment and complaint status to IN_PROGRESS. You may optionally include dispatch remarks."
        confirmText="Start Work Now"
        variant="primary"
        requireReason={false}
        reasonLabel="Initial Dispatch Remarks (Optional)"
        reasonPlaceholder="e.g. Arrived on site; verified streetlight damage..."
        isLoading={actionLoading}
        onConfirm={handleStart}
        onCancel={() => setIsStartOpen(false)}
      />

      {/* Modal: Log Progress Update */}
      {isProgressOpen && (
        <div
          className="dialog-overlay"
          onClick={() => setIsProgressOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
            <div className="dialog-header">
              <h3 className="dialog-title">Log Field Progress Milestone</h3>
              <button
                type="button"
                className="dialog-close-btn"
                onClick={() => setIsProgressOpen(false)}
                disabled={actionLoading}
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleProgressSubmit}>
              <div className="dialog-body">
                <p className="dialog-desc">
                  Record an intermediate observation, equipment requisition, or milestone for this active work order.
                </p>

                {progressError && (
                  <div style={{ marginBottom: "var(--space-3)" }}>
                    <Alert variant="error" title="Validation Error">
                      {progressError}
                    </Alert>
                  </div>
                )}

                <div className="dialog-reason-group">
                  <label className="dialog-label">
                    Progress Description <span className="required-star">*</span>
                  </label>
                  <textarea
                    className="dialog-textarea"
                    rows={4}
                    value={progressDesc}
                    placeholder="e.g. Cleared drainage blockage; pouring concrete reinforcement tomorrow morning..."
                    disabled={actionLoading}
                    onChange={(e) => setProgressDesc(e.target.value)}
                  />
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "var(--text-xs)",
                      color: "var(--color-text-muted)",
                      marginTop: 4,
                    }}
                  >
                    <span>Minimum 5 characters required</span>
                    <span>{progressDesc.length} / 2000</span>
                  </div>
                </div>
              </div>

              <div className="dialog-footer">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsProgressOpen(false)}
                  disabled={actionLoading}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={actionLoading || progressDesc.trim().length < 5}
                >
                  {actionLoading ? "Submitting..." : "Submit Progress Log"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Complete Work Order */}
      {isCompleteOpen && (
        <div
          className="dialog-overlay"
          onClick={() => setIsCompleteOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
            <div className="dialog-header">
              <h3 className="dialog-title">Submit Work Order Completion</h3>
              <button
                type="button"
                className="dialog-close-btn"
                onClick={() => setIsCompleteOpen(false)}
                disabled={actionLoading}
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCompleteSubmit}>
              <div className="dialog-body">
                <p className="dialog-desc">
                  Provide a comprehensive summary of all remediation actions taken. Submitting completion marks this assignment as <strong>COMPLETED</strong> and moves the complaint to <strong>RESOLVED_AWAITING_VERIFICATION</strong> for citizen review.
                </p>

                {completionError && (
                  <div style={{ marginBottom: "var(--space-3)" }}>
                    <Alert variant="error" title="Validation Error">
                      {completionError}
                    </Alert>
                  </div>
                )}

                <div className="dialog-reason-group">
                  <label className="dialog-label">
                    Remediation Summary <span className="required-star">*</span>
                  </label>
                  <textarea
                    className="dialog-textarea"
                    rows={4}
                    value={completionSummary}
                    placeholder="e.g. Replaced damaged water main section, pressure tested at 65 PSI, and backfilled trench..."
                    disabled={actionLoading}
                    onChange={(e) => setCompletionSummary(e.target.value)}
                  />
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "var(--text-xs)",
                      color: "var(--color-text-muted)",
                      marginTop: 4,
                    }}
                  >
                    <span>Minimum 10 characters required</span>
                    <span>{completionSummary.length} / 2000</span>
                  </div>
                </div>
              </div>

              <div className="dialog-footer">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsCompleteOpen(false)}
                  disabled={actionLoading}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={actionLoading || completionSummary.trim().length < 10}
                >
                  {actionLoading ? "Submitting..." : "Submit Completion"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
