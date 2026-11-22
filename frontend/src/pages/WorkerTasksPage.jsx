import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Link, useLocation } from "react-router-dom";
import "./DashboardPages.css";
import { workerService } from "../services/workerService";
import { ApiError } from "../types/api";
import { Card, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";
import { WorkerTaskCard } from "../components/WorkerTaskCard";
import { ConfirmationDialog } from "../components/ConfirmationDialog";

const PRIORITY_OPTIONS = [
  { label: "All Priorities", value: "" },
  { label: "Urgent", value: "URGENT" },
  { label: "High", value: "HIGH" },
  { label: "Medium", value: "MEDIUM" },
  { label: "Low", value: "LOW" },
];

export const WorkerTasksPage = ({ initialStatusFilter = "" }) => {
  const location = useLocation();

  // Determine active tab from URL path, prop, or user selection
  const currentPath = location.pathname;
  let defaultTab = initialStatusFilter || "ALL";
  if (currentPath.includes("/in-progress")) {
    defaultTab = "IN_PROGRESS";
  } else if (currentPath.includes("/completed")) {
    defaultTab = "COMPLETED";
  }

  const [userTab, setUserTab] = useState(null);
  const activeTab = userTab ?? defaultTab;
  const [priorityFilter, setPriorityFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const [tasks, setTasks] = useState([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionFeedback, setActionFeedback] = useState(null);

  // Dialog State
  const [selectedAssignmentId, setSelectedAssignmentId] = useState(null);
  const [dialogType, setDialogType] = useState(null); // 'accept' | 'start'
  const [dialogLoading, setDialogLoading] = useState(false);

  // Fetch tasks using backend pagination and filtering
  const fetchTasks = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = {
        page,
        page_size: pageSize,
      };

      // Map tab to backend status filter
      if (activeTab === "AWAITING_ACCEPTANCE" || activeTab === "ASSIGNED") {
        params.status = "ASSIGNED";
      } else if (activeTab === "IN_PROGRESS") {
        params.status = "IN_PROGRESS";
      } else if (activeTab === "COMPLETED") {
        params.status = "COMPLETED";
      }

      if (priorityFilter) {
        params.priority = priorityFilter;
      }

      const res = await workerService.getMyTasks(params);
      let items = res.data || [];

      // If Awaiting Acceptance tab, filter for !accepted_at
      if (activeTab === "AWAITING_ACCEPTANCE") {
        items = items.filter((t) => !t.accepted_at);
      }

      setTasks(items);
      setTotalItems(res.total_items || 0);
      setTotalPages(res.total_pages || 1);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || "Failed to load assigned tasks.");
      } else {
        setError("Network error. Please verify your connection.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, activeTab, priorityFilter]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Quick Accept Action
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
        message: "Work order accepted successfully.",
      });
      setDialogType(null);
      setSelectedAssignmentId(null);
      await fetchTasks();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to accept task.";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setDialogLoading(false);
    }
  };

  // Quick Start Action
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
        message: "Work initiated. Task is now In Progress.",
      });
      setDialogType(null);
      setSelectedAssignmentId(null);
      await fetchTasks();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to start work.";
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setDialogLoading(false);
    }
  };

  // Client search filter (by complaint number, title, locality)
  const filteredTasks = useMemo(() => {
    if (!searchQuery.trim()) return tasks;
    const q = searchQuery.toLowerCase().trim();
    return tasks.filter((t) => {
      const numMatch = (t.complaint_number || "").toLowerCase().includes(q);
      const titleMatch = (t.title || "").toLowerCase().includes(q);
      const locMatch = t.location
        ? [t.location.ward_or_district, t.location.city, t.location.address_line1]
            .filter(Boolean)
            .join(" ")
            .toLowerCase()
            .includes(q)
        : false;
      return numMatch || titleMatch || locMatch;
    });
  }, [tasks, searchQuery]);

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <div className="portal-phase-notice">
            <span>●</span> Field Operations Portal
          </div>
          <h1 className="portal-header-title" style={{ marginTop: "var(--space-2)" }}>
            Assigned Work Orders
          </h1>
          <p className="portal-header-subtitle">
            Manage your dispatch queue, accept pending assignments, and record resolution progress
          </p>
        </div>

        <div className="portal-header-actions">
          <Link to="/worker">
            <Button variant="secondary">
              &larr; Operations Dashboard
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

      {/* Filter Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--color-border)",
          gap: "var(--space-2)",
          marginBottom: "var(--space-4)",
          overflowX: "auto",
        }}
      >
        <button
          type="button"
          onClick={() => {
            setUserTab("ALL");
            setPage(1);
          }}
          style={{
            padding: "var(--space-3) var(--space-4)",
            background: "none",
            border: "none",
            borderBottom: activeTab === "ALL" ? "2px solid var(--color-primary)" : "2px solid transparent",
            color: activeTab === "ALL" ? "var(--color-primary)" : "var(--color-text-muted)",
            fontWeight: activeTab === "ALL" ? "var(--weight-bold)" : "var(--weight-medium)",
            cursor: "pointer",
            fontSize: "var(--text-sm)",
          }}
        >
          All Tasks
        </button>

        <button
          type="button"
          onClick={() => {
            setUserTab("AWAITING_ACCEPTANCE");
            setPage(1);
          }}
          style={{
            padding: "var(--space-3) var(--space-4)",
            background: "none",
            border: "none",
            borderBottom: activeTab === "AWAITING_ACCEPTANCE" ? "2px solid var(--color-primary)" : "2px solid transparent",
            color: activeTab === "AWAITING_ACCEPTANCE" ? "var(--color-primary)" : "var(--color-text-muted)",
            fontWeight: activeTab === "AWAITING_ACCEPTANCE" ? "var(--weight-bold)" : "var(--weight-medium)",
            cursor: "pointer",
            fontSize: "var(--text-sm)",
          }}
        >
          Awaiting Acceptance
        </button>

        <button
          type="button"
          onClick={() => {
            setUserTab("IN_PROGRESS");
            setPage(1);
          }}
          style={{
            padding: "var(--space-3) var(--space-4)",
            background: "none",
            border: "none",
            borderBottom: activeTab === "IN_PROGRESS" ? "2px solid var(--color-primary)" : "2px solid transparent",
            color: activeTab === "IN_PROGRESS" ? "var(--color-primary)" : "var(--color-text-muted)",
            fontWeight: activeTab === "IN_PROGRESS" ? "var(--weight-bold)" : "var(--weight-medium)",
            cursor: "pointer",
            fontSize: "var(--text-sm)",
          }}
        >
          In Progress
        </button>

        <button
          type="button"
          onClick={() => {
            setUserTab("COMPLETED");
            setPage(1);
          }}
          style={{
            padding: "var(--space-3) var(--space-4)",
            background: "none",
            border: "none",
            borderBottom: activeTab === "COMPLETED" ? "2px solid var(--color-primary)" : "2px solid transparent",
            color: activeTab === "COMPLETED" ? "var(--color-primary)" : "var(--color-text-muted)",
            fontWeight: activeTab === "COMPLETED" ? "var(--weight-bold)" : "var(--weight-medium)",
            cursor: "pointer",
            fontSize: "var(--text-sm)",
          }}
        >
          Completed
        </button>
      </div>

      {/* Search & Filter Toolbar */}
      <Card style={{ marginBottom: "var(--space-4)" }}>
        <CardContent>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "var(--space-3)",
            }}
          >
            {/* Search Input */}
            <div style={{ flex: "1 1 250px", position: "relative" }}>
              <input
                type="text"
                placeholder="Search reference, title, or ward..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--color-border)",
                  fontSize: "var(--text-sm)",
                  color: "var(--color-text-main)",
                  outline: "none",
                }}
              />
            </div>

            {/* Priority Filter */}
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <label
                style={{
                  fontSize: "var(--text-xs)",
                  fontWeight: "var(--weight-bold)",
                  color: "var(--color-text-muted)",
                  textTransform: "uppercase",
                }}
              >
                Priority:
              </label>
              <select
                value={priorityFilter}
                onChange={(e) => {
                  setPriorityFilter(e.target.value);
                  setPage(1);
                }}
                style={{
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--color-border)",
                  fontSize: "var(--text-sm)",
                  background: "#fff",
                  color: "var(--color-text-main)",
                  cursor: "pointer",
                }}
              >
                {PRIORITY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>

              {(priorityFilter || searchQuery) && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setPriorityFilter("");
                    setSearchQuery("");
                    setPage(1);
                  }}
                >
                  Clear Filters
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error state */}
      {error && (
        <Alert variant="error" title="Queue Error">
          {error}
          <div style={{ marginTop: "var(--space-2)" }}>
            <Button variant="outline" size="sm" onClick={fetchTasks}>
              Retry Loading Tasks
            </Button>
          </div>
        </Alert>
      )}

      {/* Loading state */}
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
            Loading assigned task records...
          </span>
        </div>
      )}

      {/* Task List */}
      {!isLoading && !error && (
        <>
          {filteredTasks.length === 0 ? (
            <Card>
              <CardContent>
                <EmptyState
                  title="No Tasks Found"
                  description={
                    searchQuery || priorityFilter
                      ? "No assigned tasks match your selected filter criteria. Try resetting your search or priority filter."
                      : "You have no work orders in this category."
                  }
                  action={
                    (searchQuery || priorityFilter) ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setPriorityFilter("");
                          setSearchQuery("");
                        }}
                      >
                        Reset Filters
                      </Button>
                    ) : (
                      <Button variant="secondary" size="sm" onClick={fetchTasks}>
                        Refresh Queue
                      </Button>
                    )
                  }
                />
              </CardContent>
            </Card>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-4)",
              }}
            >
              {filteredTasks.map((task) => (
                <WorkerTaskCard
                  key={task.assignment_id}
                  task={task}
                  onAccept={promptAccept}
                  onStart={promptStart}
                  actionLoading={dialogLoading}
                />
              ))}

              {/* Server-side Pagination */}
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                totalItems={totalItems}
                pageSize={pageSize}
                onPageChange={(p) => setPage(p)}
              />
            </div>
          )}
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
