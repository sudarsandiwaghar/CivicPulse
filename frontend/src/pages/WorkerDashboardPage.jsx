import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import "./DashboardPages.css";
import { useAuth } from "../hooks/useAuth";
import { workerService } from "../services/workerService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { StatCard } from "../components/StatCard";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { WorkerTaskCard } from "../components/WorkerTaskCard";
import { ConfirmationDialog } from "../components/ConfirmationDialog";

export const WorkerDashboardPage = () => {
  const { user } = useAuth();

  const [metrics, setMetrics] = useState({
    totalCount: 0,
    pendingAcceptanceCount: 0,
    acceptedPendingStartCount: 0,
    inProgressCount: 0,
    completedCount: 0,
    recentTasks: [],
  });

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionFeedback, setActionFeedback] = useState(null);

  // Dialog State
  const [selectedAssignmentId, setSelectedAssignmentId] = useState(null);
  const [dialogType, setDialogType] = useState(null); // 'accept' | 'start'
  const [dialogLoading, setDialogLoading] = useState(false);

  const fetchDashboardData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await workerService.getDashboardMetrics();
      setMetrics(data);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.statusCode === 403) {
          setError(
            "Access Denied: Only active field workers can inspect the operational dispatch dashboard."
          );
        } else {
          setError(err.message || "Failed to load worker dashboard metrics.");
        }
      } else {
        setError("Network error. Please verify your connection.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Handle Quick Accept Confirmation
  const promptAccept = (assignmentId) => {
    setSelectedAssignmentId(assignmentId);
    setDialogType("accept");
  };

  const handleConfirmAccept = async () => {
    if (!selectedAssignmentId) return;
    setDialogLoading(true);
    setActionFeedback(null);
    try {
      await workerService.acceptTask(selectedAssignmentId);
      setActionFeedback({
        type: "success",
        message: "Work order successfully accepted. You may now proceed on site.",
      });
      setDialogType(null);
      setSelectedAssignmentId(null);
      await fetchDashboardData();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to accept task.";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setDialogLoading(false);
    }
  };

  // Handle Quick Start Confirmation
  const promptStart = (assignmentId) => {
    setSelectedAssignmentId(assignmentId);
    setDialogType("start");
  };

  const handleConfirmStart = async (notes) => {
    if (!selectedAssignmentId) return;
    setDialogLoading(true);
    setActionFeedback(null);
    try {
      await workerService.startTask(selectedAssignmentId, notes);
      setActionFeedback({
        type: "success",
        message: "Work order started. Complaint and assignment moved to In Progress.",
      });
      setDialogType(null);
      setSelectedAssignmentId(null);
      await fetchDashboardData();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to start work.";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setDialogLoading(false);
    }
  };

  // Partition tasks requiring attention (Pending Acceptance or In Progress)
  const urgentAttentionTasks = metrics.recentTasks.filter(
    (t) =>
      (t.assignment_status === "ASSIGNED" && !t.accepted_at) ||
      t.priority === "URGENT" ||
      t.priority === "HIGH"
  );

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <div className="portal-phase-notice">
            <span>●</span> Field Operations Portal
          </div>
          <h1 className="portal-header-title" style={{ marginTop: "var(--space-2)" }}>
            Welcome, {user?.full_name || "Field Officer"}
          </h1>
          <p className="portal-header-subtitle">
            Inspect assigned work orders, accept dispatch tasks, log milestone updates, and submit resolution summaries
          </p>
        </div>
        <div className="portal-header-actions">
          <Link to="/worker/tasks">
            <Button variant="primary">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ marginRight: 6 }}
              >
                <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
                <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
              </svg>
              View All Tasks ({metrics.totalCount})
            </Button>
          </Link>
          <Link to="/worker/tasks/in-progress">
            <Button variant="secondary">
              Active Investigations ({metrics.inProgressCount})
            </Button>
          </Link>
        </div>
      </div>

      {/* Global Feedback Banner */}
      {actionFeedback && (
        <Alert
          variant={actionFeedback.type}
          title={actionFeedback.type === "success" ? "Success" : "Error"}
          onClose={() => setActionFeedback(null)}
        >
          {actionFeedback.message}
        </Alert>
      )}

      {/* Error state */}
      {error && (
        <Alert variant="error" title="Dashboard Error">
          {error}
          <div style={{ marginTop: "var(--space-2)" }}>
            <Button variant="outline" size="sm" onClick={fetchDashboardData}>
              Retry Loading Dashboard
            </Button>
          </div>
        </Alert>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "var(--space-8)",
            minHeight: "40vh",
          }}
        >
          <Spinner size="lg" />
          <span
            style={{
              marginTop: "var(--space-3)",
              color: "var(--color-text-muted)",
              fontSize: "var(--text-sm)",
            }}
          >
            Retrieving operational task queues and metrics...
          </span>
        </div>
      )}

      {!isLoading && !error && (
        <>
          {/* Operational Metrics Grid */}
          <div className="portal-stats-grid">
            <StatCard
              title="Total Assigned"
              value={metrics.totalCount.toString()}
              change="Work orders on record"
              changeType="neutral"
              icon={
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
                  <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
                </svg>
              }
            />

            <StatCard
              title="Pending Acceptance"
              value={metrics.pendingAcceptanceCount.toString()}
              change="Requires technician receipt"
              changeType={metrics.pendingAcceptanceCount > 0 ? "negative" : "positive"}
              icon={
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              }
            />

            <StatCard
              title="In Progress"
              value={metrics.inProgressCount.toString()}
              change="Active on-site resolution"
              changeType="neutral"
              icon={
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              }
            />

            <StatCard
              title="Completed Work Orders"
              value={metrics.completedCount.toString()}
              change="Submitted for verification"
              changeType="positive"
              icon={
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              }
            />
          </div>

          {/* Attention Required Section */}
          {urgentAttentionTasks.length > 0 && (
            <div style={{ marginTop: "var(--space-6)" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "var(--space-3)",
                }}
              >
                <h2
                  style={{
                    fontSize: "var(--text-lg)",
                    fontWeight: "var(--weight-bold)",
                    color: "var(--color-tertiary)",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-2)",
                  }}
                >
                  <span style={{ color: "#B45309" }}>⚠</span> Tasks Requiring Immediate Attention
                </h2>
                <Link
                  to="/worker/tasks"
                  style={{
                    fontSize: "var(--text-xs)",
                    fontWeight: "var(--weight-bold)",
                    color: "var(--color-primary)",
                    textDecoration: "none",
                  }}
                >
                  View All &rarr;
                </Link>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                  gap: "var(--space-4)",
                }}
              >
                {urgentAttentionTasks.slice(0, 3).map((task) => (
                  <WorkerTaskCard
                    key={task.assignment_id}
                    task={task}
                    onAccept={promptAccept}
                    onStart={promptStart}
                    actionLoading={dialogLoading}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Recent Task Dispatch Queue */}
          <div style={{ marginTop: "var(--space-6)" }}>
            <Card>
              <CardHeader>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    width: "100%",
                  }}
                >
                  <CardTitle>Recent Dispatch Activity</CardTitle>
                  <Link
                    to="/worker/tasks"
                    style={{
                      fontSize: "var(--text-xs)",
                      fontWeight: "var(--weight-bold)",
                      color: "var(--color-primary)",
                      textDecoration: "none",
                    }}
                  >
                    Go to Full Queue &rarr;
                  </Link>
                </div>
              </CardHeader>
              <CardContent>
                {metrics.recentTasks.length === 0 ? (
                  <EmptyState
                    title="No Assigned Work Orders"
                    description="When municipal administrators dispatch complaints matching your department coverage, they will appear in this queue."
                    action={
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={fetchDashboardData}
                      >
                        Refresh Queue
                      </Button>
                    }
                  />
                ) : (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "var(--space-3)",
                    }}
                  >
                    {metrics.recentTasks.map((task) => (
                      <WorkerTaskCard
                        key={task.assignment_id}
                        task={task}
                        onAccept={promptAccept}
                        onStart={promptStart}
                        actionLoading={dialogLoading}
                      />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {/* Confirmation Dialog: Accept Assignment */}
      <ConfirmationDialog
        isOpen={dialogType === "accept"}
        title="Accept Work Order Assignment"
        description="Acknowledge receipt of this assigned civic complaint. The administrator and reporting citizen will receive an operational receipt confirmation."
        confirmText="Confirm Acceptance"
        variant="primary"
        isLoading={dialogLoading}
        onConfirm={handleConfirmAccept}
        onCancel={() => {
          setDialogType(null);
          setSelectedAssignmentId(null);
        }}
      />

      {/* Confirmation Dialog: Start Work */}
      <ConfirmationDialog
        isOpen={dialogType === "start"}
        title="Initiate Work On Site"
        description="Starting work moves this assignment and complaint to IN_PROGRESS status. You may optionally provide preliminary on-site observations."
        confirmText="Start Work Now"
        variant="primary"
        requireReason={false}
        reasonLabel="Initial Dispatch Remarks (Optional)"
        reasonPlaceholder="e.g. Arrived on site; perimeter secured..."
        isLoading={dialogLoading}
        onConfirm={handleConfirmStart}
        onCancel={() => {
          setDialogType(null);
          setSelectedAssignmentId(null);
        }}
      />
    </div>
  );
};
