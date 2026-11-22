import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import "./DashboardPages.css";
import { slaService } from "../services/slaService";
import { adminService } from "../services/adminService";
import { categoryService } from "../services/categoryService";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { StatusBadge } from "../components/StatusBadge";
import { ConfirmationDialog } from "../components/ConfirmationDialog";

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

function getTimeRemaining(deadlineStr) {
  if (!deadlineStr) return "No deadline set";
  try {
    const diffMs = new Date(deadlineStr).getTime() - Date.now();
    const isPast = diffMs < 0;
    const absMs = Math.abs(diffMs);
    const hours = Math.floor(absMs / (1000 * 60 * 60));
    const mins = Math.floor((absMs % (1000 * 60 * 60)) / (1000 * 60));

    if (isPast) {
      return `Overdue by ${hours}h ${mins}m`;
    }
    return `${hours}h ${mins}m remaining`;
  } catch {
    return deadlineStr;
  }
}

export const AdminSLADashboardPage = () => {
  const [complaintSLAs, setComplaintSLAs] = useState([]);
  const [categories, setCategories] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [evaluating, setEvaluating] = useState(false);
  const [isConfirmEvalOpen, setIsConfirmEvalOpen] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [escalationFilter, setEscalationFilter] = useState("ALL"); // ALL | BREACHED | WARNING | NORMAL
  const [activeTab, setActiveTab] = useState("ALL"); // ALL | RESPONSE_WATCH | RESOLUTION_WATCH | ESCALATED | PAUSED

  // Load categories
  useEffect(() => {
    categoryService.getCategories().then(setCategories).catch(() => {});
  }, []);

  // Fetch monitored complaints and their live SLA details
  const fetchSLAMonitoring = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Fetch active/recent complaints (up to 60 for rich dashboard monitoring)
      const res = await adminService.listComplaints({
        page: 1,
        page_size: 60,
        sort_by: "created_at",
        sort_order: "desc",
      });
      const items = res.data || [];

      // 2. Fetch live dual-clock SLA details for each complaint in parallel
      const slaResults = await Promise.all(
        items.map(async (c) => {
          try {
            const sla = await slaService.getComplaintSLA(c.id);
            return {
              ...c,
              sla,
            };
          } catch {
            return {
              ...c,
              sla: null,
            };
          }
        })
      );

      setComplaintSLAs(slaResults);
    } catch (err) {
      setError(err.message || "Failed to load SLA monitoring records.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSLAMonitoring();
  }, [fetchSLAMonitoring]);

  // Run On-Demand Batch SLA Evaluation
  const handleRunEvaluation = async () => {
    setIsConfirmEvalOpen(false);
    setEvaluating(true);
    setFeedback(null);
    try {
      const evalRes = await slaService.evaluateBatch({
        limit: 100,
      });

      setFeedback({
        type: "success",
        message: `Batch evaluation complete: ${evalRes.evaluated_count} active complaints evaluated (${evalRes.escalated_count} escalation transition(s), ${evalRes.breached_count || 0} breaches confirmed). Backend state updated.`,
      });

      await fetchSLAMonitoring();
    } catch (err) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to execute batch SLA evaluation.",
      });
    } finally {
      setEvaluating(false);
    }
  };

  // Derive Overview Metrics from actual backend SLA data
  const metrics = useMemo(() => {
    const totalMonitored = complaintSLAs.length;

    // Response Clock Metrics
    let respWithinSLA = 0;
    let respApproaching = 0;
    let respBreached = 0;
    let respMet = 0;

    // Resolution Clock Metrics
    let resWithinSLA = 0;
    let resApproaching = 0;
    let resBreached = 0;
    let resMet = 0;

    // Escalated & Paused
    let escalatedCount = 0;
    let pausedCount = 0;

    complaintSLAs.forEach((c) => {
      const s = c.sla;
      if (!s) return;

      // Response clock evaluation
      if (s.responded_at) {
        respMet += 1;
        if (!s.response_breached) respWithinSLA += 1;
        else respBreached += 1;
      } else if (s.response_breached || s.response_escalation_level >= 2) {
        respBreached += 1;
      } else if (s.response_escalation_level === 1) {
        respApproaching += 1;
        respWithinSLA += 1;
      } else {
        respWithinSLA += 1;
      }

      // Resolution clock evaluation
      if (s.resolved_at) {
        resMet += 1;
        if (!s.resolution_breached) resWithinSLA += 1;
        else resBreached += 1;
      } else if (s.resolution_breached || s.resolution_escalation_level >= 2) {
        resBreached += 1;
      } else if (s.resolution_escalation_level === 1) {
        resApproaching += 1;
        resWithinSLA += 1;
      } else {
        resWithinSLA += 1;
      }

      // Escalation checks
      if (s.response_escalation_level > 0 || s.resolution_escalation_level > 0) {
        escalatedCount += 1;
      }

      // Paused checks
      if (c.status === "ON_HOLD" || s.response_pause_started_at || s.resolution_pause_started_at || (s.response_pause_duration_seconds > 0 || s.resolution_pause_duration_seconds > 0)) {
        pausedCount += 1;
      }
    });

    return {
      totalMonitored,
      respWithinSLA,
      respApproaching,
      respBreached,
      respMet,
      resWithinSLA,
      resApproaching,
      resBreached,
      resMet,
      escalatedCount,
      pausedCount,
    };
  }, [complaintSLAs]);

  // Client filtering
  const filteredComplaints = useMemo(() => {
    return complaintSLAs.filter((c) => {
      const s = c.sla;

      // Status filter
      if (statusFilter !== "ALL" && c.status !== statusFilter) return false;

      // Priority filter
      if (priorityFilter && c.priority !== priorityFilter) return false;

      // Category filter
      if (categoryFilter && String(c.category_id) !== String(categoryFilter)) return false;

      // Escalation filter
      if (escalationFilter === "BREACHED") {
        if (!s || (!s.response_breached && !s.resolution_breached && s.response_escalation_level < 2 && s.resolution_escalation_level < 2)) {
          return false;
        }
      } else if (escalationFilter === "WARNING") {
        if (!s || (s.response_escalation_level !== 1 && s.resolution_escalation_level !== 1)) {
          return false;
        }
      } else if (escalationFilter === "NORMAL") {
        if (s && (s.response_escalation_level > 0 || s.resolution_escalation_level > 0 || s.response_breached || s.resolution_breached)) {
          return false;
        }
      }

      // Tab scoping
      if (activeTab === "RESPONSE_WATCH") {
        // Pending response clock
        if (!s || s.responded_at || ["CLOSED", "REJECTED", "DUPLICATE"].includes(c.status)) return false;
      } else if (activeTab === "RESOLUTION_WATCH") {
        // Active resolution clock
        if (!s || s.resolved_at || ["CLOSED", "REJECTED", "DUPLICATE"].includes(c.status)) return false;
      } else if (activeTab === "ESCALATED") {
        if (!s || (s.response_escalation_level === 0 && s.resolution_escalation_level === 0)) return false;
      } else if (activeTab === "PAUSED") {
        if (c.status !== "ON_HOLD" && !s?.response_pause_started_at && !s?.resolution_pause_started_at) return false;
      }

      return true;
    });
  }, [complaintSLAs, statusFilter, priorityFilter, categoryFilter, escalationFilter, activeTab]);

  return (
    <div className="portal-page">
      {/* Top Header */}
      <div className="portal-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <h1 className="portal-header-title">SLA Performance Monitoring</h1>
          </div>
          <p className="portal-header-subtitle">
            Dual-clock SLA oversight tracking initial response deadlines, field resolution targets, pause accumulation, and automatic escalations.
          </p>
        </div>

        <div className="portal-header-actions" style={{ flexWrap: "wrap" }}>
          <Link to="/admin/sla/policies">
            <Button variant="outline">
              Manage SLA Policies &rarr;
            </Button>
          </Link>
          <Button
            variant="primary"
            disabled={evaluating || isLoading}
            onClick={() => setIsConfirmEvalOpen(true)}
          >
            {evaluating ? "Evaluating Clocks..." : "Run On-Demand SLA Evaluation"}
          </Button>
        </div>
      </div>

      {feedback && (
        <Alert
          variant={feedback.type}
          dismissible
          onDismiss={() => setFeedback(null)}
        >
          {feedback.message}
        </Alert>
      )}

      {/* Primary Dual-Clock Overview Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
        {/* Response SLA Clock Card */}
        <Card>
          <CardHeader>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <CardTitle>Response SLA Clock (Initial Triage)</CardTitle>
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: "700",
                  textTransform: "uppercase",
                  padding: "2px 8px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: "#e0f2fe",
                  color: "#0369a1",
                }}
              >
                Inception &rarr; Under Review
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", textAlign: "center" }}>
              <div style={{ padding: "0.75rem", backgroundColor: "#f0fdf4", borderRadius: "var(--radius-md)", border: "1px solid #bbf7d0" }}>
                <div style={{ fontSize: "1.5rem", fontWeight: "700", color: "#15803d" }}>
                  {metrics.respWithinSLA}
                </div>
                <div style={{ fontSize: "0.75rem", color: "#166534", fontWeight: "600", marginTop: "2px" }}>
                  Within Target
                </div>
              </div>

              <div style={{ padding: "0.75rem", backgroundColor: "#fefce8", borderRadius: "var(--radius-md)", border: "1px solid #fef08a" }}>
                <div style={{ fontSize: "1.5rem", fontWeight: "700", color: "#a16207" }}>
                  {metrics.respApproaching}
                </div>
                <div style={{ fontSize: "0.75rem", color: "#854d0e", fontWeight: "600", marginTop: "2px" }}>
                  Warning (75%)
                </div>
              </div>

              <div style={{ padding: "0.75rem", backgroundColor: "#fef2f2", borderRadius: "var(--radius-md)", border: "1px solid #fecaca" }}>
                <div style={{ fontSize: "1.5rem", fontWeight: "700", color: "#b91c1c" }}>
                  {metrics.respBreached}
                </div>
                <div style={{ fontSize: "0.75rem", color: "#991b1b", fontWeight: "600", marginTop: "2px" }}>
                  Breached (&ge;100%)
                </div>
              </div>
            </div>
            <div style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "var(--color-text-muted)", textAlign: "right" }}>
              Completed & Met: <strong>{metrics.respMet}</strong> complaints
            </div>
          </CardContent>
        </Card>

        {/* Resolution SLA Clock Card */}
        <Card>
          <CardHeader>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <CardTitle>Resolution SLA Clock (Remediation)</CardTitle>
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: "700",
                  textTransform: "uppercase",
                  padding: "2px 8px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: "#f3e8ff",
                  color: "#7e22ce",
                }}
              >
                Inception &rarr; Resolved
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", textAlign: "center" }}>
              <div style={{ padding: "0.75rem", backgroundColor: "#f0fdf4", borderRadius: "var(--radius-md)", border: "1px solid #bbf7d0" }}>
                <div style={{ fontSize: "1.5rem", fontWeight: "700", color: "#15803d" }}>
                  {metrics.resWithinSLA}
                </div>
                <div style={{ fontSize: "0.75rem", color: "#166534", fontWeight: "600", marginTop: "2px" }}>
                  On Schedule
                </div>
              </div>

              <div style={{ padding: "0.75rem", backgroundColor: "#fefce8", borderRadius: "var(--radius-md)", border: "1px solid #fef08a" }}>
                <div style={{ fontSize: "1.5rem", fontWeight: "700", color: "#a16207" }}>
                  {metrics.resApproaching}
                </div>
                <div style={{ fontSize: "0.75rem", color: "#854d0e", fontWeight: "600", marginTop: "2px" }}>
                  Warning (75%)
                </div>
              </div>

              <div style={{ padding: "0.75rem", backgroundColor: "#fef2f2", borderRadius: "var(--radius-md)", border: "1px solid #fecaca" }}>
                <div style={{ fontSize: "1.5rem", fontWeight: "700", color: "#b91c1c" }}>
                  {metrics.resBreached}
                </div>
                <div style={{ fontSize: "0.75rem", color: "#991b1b", fontWeight: "600", marginTop: "2px" }}>
                  Breached (&ge;100%)
                </div>
              </div>
            </div>
            <div style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "var(--color-text-muted)", textAlign: "right" }}>
              Completed & Resolved: <strong>{metrics.resMet}</strong> complaints
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Summary KPI Strip */}
      <div className="portal-stats-grid">
        <Card>
          <CardContent style={{ padding: "1rem 1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Total Monitored Cases
            </span>
            <div style={{ fontSize: "1.5rem", fontWeight: "700", color: "var(--color-text-main)", marginTop: "0.25rem" }}>
              {metrics.totalMonitored}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Active complaint lifecycle</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1rem 1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Escalated Complaints
            </span>
            <div style={{ fontSize: "1.5rem", fontWeight: "700", color: metrics.escalatedCount > 0 ? "#b91c1c" : "#15803d", marginTop: "0.25rem" }}>
              {metrics.escalatedCount}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Escalation Level &ge; 1</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1rem 1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Paused Cases (Hold)
            </span>
            <div style={{ fontSize: "1.5rem", fontWeight: "700", color: "#087f8c", marginTop: "0.25rem" }}>
              {metrics.pausedCount}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Clocks frozen in ON_HOLD</span>
          </CardContent>
        </Card>
      </div>

      {/* Filter Toolbar */}
      <Card>
        {/* Navigation Tabs */}
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid var(--color-border-card)",
            padding: "0 1.25rem",
            gap: "1.5rem",
            overflowX: "auto",
          }}
        >
          <button
            onClick={() => setActiveTab("ALL")}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "ALL" ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: activeTab === "ALL" ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: activeTab === "ALL" ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            All Monitored ({complaintSLAs.length})
          </button>

          <button
            onClick={() => setActiveTab("RESPONSE_WATCH")}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "RESPONSE_WATCH" ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: activeTab === "RESPONSE_WATCH" ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: activeTab === "RESPONSE_WATCH" ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            Response Watch (Pending Triage)
          </button>

          <button
            onClick={() => setActiveTab("RESOLUTION_WATCH")}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "RESOLUTION_WATCH" ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: activeTab === "RESOLUTION_WATCH" ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: activeTab === "RESOLUTION_WATCH" ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            Resolution Watch (In Progress)
          </button>

          <button
            onClick={() => setActiveTab("ESCALATED")}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "ESCALATED" ? "2px solid #b91c1c" : "2px solid transparent",
              color: activeTab === "ESCALATED" ? "#b91c1c" : "var(--color-text-muted)",
              fontWeight: activeTab === "ESCALATED" ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            Escalated & Breached ({metrics.escalatedCount})
          </button>

          <button
            onClick={() => setActiveTab("PAUSED")}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "PAUSED" ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: activeTab === "PAUSED" ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: activeTab === "PAUSED" ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            Paused Cases ({metrics.pausedCount})
          </button>
        </div>

        <CardContent style={{ padding: "1rem 1.25rem" }}>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.75rem",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <option value="ALL">All Lifecycle Statuses</option>
                <option value="SUBMITTED">SUBMITTED</option>
                <option value="UNDER_REVIEW">UNDER_REVIEW</option>
                <option value="ASSIGNED">ASSIGNED</option>
                <option value="IN_PROGRESS">IN_PROGRESS</option>
                <option value="ON_HOLD">ON_HOLD</option>
                <option value="RESOLVED_AWAITING_VERIFICATION">RESOLVED</option>
                <option value="CLOSED">CLOSED</option>
              </select>

              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                style={{
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <option value="">All Priorities</option>
                <option value="URGENT">Urgent</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>

              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                style={{
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <option value="">All Categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>

              <select
                value={escalationFilter}
                onChange={(e) => setEscalationFilter(e.target.value)}
                style={{
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <option value="ALL">All Escalation States</option>
                <option value="BREACHED">Breached Only (&ge; 100%)</option>
                <option value="WARNING">Warnings Only (75% - 99%)</option>
                <option value="NORMAL">Normal / Within Target</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* SLA Monitored Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            SLA Monitored Complaints ({filteredComplaints.length} cases)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div style={{ padding: "3rem 0", textAlign: "center" }}>
              <Spinner size="md" message="Evaluating live dual-clock SLA metrics..." />
            </div>
          ) : error ? (
            <Alert variant="error">{error}</Alert>
          ) : filteredComplaints.length === 0 ? (
            <div style={{ padding: "3rem 0", textAlign: "center", color: "var(--color-text-muted)" }}>
              No complaints match the current SLA monitoring filters.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--color-border-card)", textAlign: "left", color: "var(--color-text-muted)" }}>
                    <th style={{ padding: "0.75rem" }}>Complaint</th>
                    <th style={{ padding: "0.75rem" }}>Status & Priority</th>
                    <th style={{ padding: "0.75rem" }}>Response Clock</th>
                    <th style={{ padding: "0.75rem" }}>Resolution Clock</th>
                    <th style={{ padding: "0.75rem" }}>Escalation Level</th>
                    <th style={{ padding: "0.75rem" }}>Pause Status</th>
                    <th style={{ padding: "0.75rem", textAlign: "right" }}>Dossier</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredComplaints.map((c) => {
                    const s = c.sla;
                    const respBreached = s?.response_breached || s?.response_escalation_level >= 2;
                    const resBreached = s?.resolution_breached || s?.resolution_escalation_level >= 2;
                    const isPaused = c.status === "ON_HOLD" || s?.response_pause_started_at || s?.resolution_pause_started_at;

                    return (
                      <tr key={c.id} style={{ borderBottom: "1px solid var(--color-border-card)" }}>
                        <td style={{ padding: "0.75rem" }}>
                          <Link
                            to={`/admin/complaints/${c.id}`}
                            style={{ fontWeight: "700", color: "var(--color-primary)", textDecoration: "none" }}
                          >
                            {c.complaint_number}
                          </Link>
                          <div style={{ fontSize: "0.75rem", color: "var(--color-text-main)", maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {c.title}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                            Category: {c.category_name}
                          </div>
                        </td>

                        <td style={{ padding: "0.75rem" }}>
                          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                            <StatusBadge status={c.status} size="sm" />
                            <span
                              style={{
                                fontSize: "0.75rem",
                                fontWeight: "600",
                                textTransform: "uppercase",
                                color:
                                  c.priority === "URGENT"
                                    ? "#b91c1c"
                                    : c.priority === "HIGH"
                                    ? "#b45309"
                                    : "#475569",
                              }}
                            >
                              {c.priority}
                            </span>
                          </div>
                        </td>

                        {/* Response Clock Cell */}
                        <td style={{ padding: "0.75rem" }}>
                          {s ? (
                            <div>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <span
                                  style={{
                                    fontSize: "0.75rem",
                                    fontWeight: "700",
                                    padding: "1px 6px",
                                    borderRadius: "var(--radius-sm)",
                                    backgroundColor: s.responded_at
                                      ? "#dcfce7"
                                      : respBreached
                                      ? "#fee2e2"
                                      : s.response_escalation_level === 1
                                      ? "#fef3c7"
                                      : "#f1f5f9",
                                    color: s.responded_at
                                      ? "#15803d"
                                      : respBreached
                                      ? "#b91c1c"
                                      : s.response_escalation_level === 1
                                      ? "#b45309"
                                      : "#475569",
                                  }}
                                >
                                  {s.responded_at
                                    ? "MET"
                                    : respBreached
                                    ? "BREACHED"
                                    : s.response_escalation_level === 1
                                    ? "WARNING"
                                    : "ON TRACK"}
                                </span>
                              </div>
                              <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: "2px" }}>
                                {s.responded_at ? (
                                  `Responded: ${formatDate(s.responded_at)}`
                                ) : s.response_deadline ? (
                                  getTimeRemaining(s.response_deadline)
                                ) : (
                                  "No target"
                                )}
                              </div>
                            </div>
                          ) : (
                            <span style={{ color: "var(--color-text-muted)", fontSize: "0.75rem" }}>—</span>
                          )}
                        </td>

                        {/* Resolution Clock Cell */}
                        <td style={{ padding: "0.75rem" }}>
                          {s ? (
                            <div>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <span
                                  style={{
                                    fontSize: "0.75rem",
                                    fontWeight: "700",
                                    padding: "1px 6px",
                                    borderRadius: "var(--radius-sm)",
                                    backgroundColor: s.resolved_at
                                      ? "#dcfce7"
                                      : resBreached
                                      ? "#fee2e2"
                                      : s.resolution_escalation_level === 1
                                      ? "#fef3c7"
                                      : "#f1f5f9",
                                    color: s.resolved_at
                                      ? "#15803d"
                                      : resBreached
                                      ? "#b91c1c"
                                      : s.resolution_escalation_level === 1
                                      ? "#b45309"
                                      : "#475569",
                                  }}
                                >
                                  {s.resolved_at
                                    ? "RESOLVED"
                                    : resBreached
                                    ? "BREACHED"
                                    : s.resolution_escalation_level === 1
                                    ? "WARNING"
                                    : "ACTIVE"}
                                </span>
                              </div>
                              <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: "2px" }}>
                                {s.resolved_at ? (
                                  `Resolved: ${formatDate(s.resolved_at)}`
                                ) : s.resolution_deadline ? (
                                  getTimeRemaining(s.resolution_deadline)
                                ) : (
                                  "No target"
                                )}
                              </div>
                            </div>
                          ) : (
                            <span style={{ color: "var(--color-text-muted)", fontSize: "0.75rem" }}>—</span>
                          )}
                        </td>

                        {/* Escalation Level */}
                        <td style={{ padding: "0.75rem" }}>
                          {s ? (
                            <div style={{ fontSize: "0.8125rem" }}>
                              <div>Resp: <strong>L{s.response_escalation_level}</strong></div>
                              <div>Res: <strong>L{s.resolution_escalation_level}</strong></div>
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>

                        {/* Pause Duration */}
                        <td style={{ padding: "0.75rem" }}>
                          {isPaused ? (
                            <span
                              style={{
                                fontSize: "0.75rem",
                                fontWeight: "700",
                                padding: "2px 6px",
                                borderRadius: "var(--radius-sm)",
                                backgroundColor: "#ffedd5",
                                color: "#c2410c",
                              }}
                            >
                              FROZEN (ON_HOLD)
                            </span>
                          ) : (
                            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                              {s && (s.response_pause_duration_seconds > 0 || s.resolution_pause_duration_seconds > 0)
                                ? `${Math.round(((s.response_pause_duration_seconds || s.resolution_pause_duration_seconds) / 3600) * 10) / 10}h paused`
                                : "No pauses"}
                            </span>
                          )}
                        </td>

                        {/* Actions */}
                        <td style={{ padding: "0.75rem", textAlign: "right" }}>
                          <Link to={`/admin/complaints/${c.id}`}>
                            <Button variant="outline" size="sm">
                              Inspect Dossier
                            </Button>
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* SLA Batch Evaluation Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={isConfirmEvalOpen}
        title="Execute On-Demand SLA Batch Evaluation?"
        description="This operation mutates backend state: it recalculates elapsed response and resolution SLA deadlines across up to 100 active complaints, triggers automated escalation warnings (Level 1) or breaches (Level 2), and creates system audit events. Note: Background evaluation does not run as a standing daemon; evaluations occur on-demand and during complaint lifecycle transitions."
        confirmText="Execute Batch Evaluation"
        cancelText="Cancel"
        variant="primary"
        isLoading={evaluating}
        onConfirm={handleRunEvaluation}
        onCancel={() => setIsConfirmEvalOpen(false)}
      />
    </div>
  );
};

export default AdminSLADashboardPage;
