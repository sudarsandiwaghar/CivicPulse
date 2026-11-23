import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import "./DashboardPages.css";
import { useAuth } from "../hooks/useAuth";
import { adminService } from "../services/adminService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { StatCard } from "../components/StatCard";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";

function formatDate(dateStr) {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export const AdminDashboardPage = () => {
  const { user } = useAuth();

  const [metrics, setMetrics] = useState({
    total: 0,
    submitted: 0,
    underReview: 0,
    assigned: 0,
    inProgress: 0,
    resolvedAwaitingVerification: 0,
    closed: 0,
    rejected: 0,
    recentComplaints: [],
    urgentComplaints: [],
  });

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDashboardData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminService.getDashboardMetrics();
      setMetrics(data);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.statusCode === 403) {
          setError("Access Denied: Only platform administrators can inspect the Command Center.");
        } else {
          setError(err.message || "Failed to load administrator dashboard metrics.");
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

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <div className="portal-phase-notice">
            <span>●</span> Administrator Command Portal
          </div>
          <h1 className="portal-header-title" style={{ marginTop: "var(--space-2)" }}>
            Municipal Operations Center
          </h1>
          <p className="portal-header-subtitle">
            Welcome back, {user?.full_name || "Administrator"} — Monitor real-time complaint triage queues, workforce deployment, and municipal resolution pipelines
          </p>
        </div>
        <div className="portal-header-actions">
          <Link to="/admin/complaints">
            <Button variant="primary">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              Complaints Triage Queue ({metrics.submitted})
            </Button>
          </Link>
          <Link to="/admin/workers">
            <Button variant="secondary">
              Field Workforce
            </Button>
          </Link>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <Alert variant="error" title="Dashboard Error">
          {typeof error === "string" ? error : (error?.message || JSON.stringify(error))}
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
          <span style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
            Aggregating platform complaint statistics and municipal triage queues...
          </span>
        </div>
      )}

      {!isLoading && !error && (
        <>
          {/* Operational Metrics Grid */}
          <div className="portal-stats-grid">
            <StatCard
              title="Total Complaints"
              value={metrics.total.toString()}
              change="Platform lifetime submissions"
              changeType="neutral"
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
              }
            />

            <StatCard
              title="Pending Triage"
              value={metrics.submitted.toString()}
              change="Newly submitted, awaiting review"
              changeType={metrics.submitted > 0 ? "negative" : "positive"}
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              }
            />

            <StatCard
              title="Under Review"
              value={metrics.underReview.toString()}
              change="Ready for worker dispatch"
              changeType="neutral"
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>
              }
            />

            <StatCard
              title="Active Work Orders"
              value={(metrics.assigned + metrics.inProgress).toString()}
              change={`${metrics.inProgress} on site, ${metrics.assigned} dispatched`}
              changeType="positive"
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              }
            />
          </div>

          {/* Secondary Metric Bar */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "var(--space-3)",
              marginTop: "var(--space-4)",
            }}
          >
            <div style={{ padding: "var(--space-3)", backgroundColor: "var(--color-bg-card)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)" }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>Awaiting Verification</span>
              <strong style={{ fontSize: "var(--text-lg)", color: "var(--color-tertiary)" }}>{metrics.resolvedAwaitingVerification}</strong>
            </div>

            <div style={{ padding: "var(--space-3)", backgroundColor: "var(--color-bg-card)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)" }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>Verified & Closed</span>
              <strong style={{ fontSize: "var(--text-lg)", color: "#059669" }}>{metrics.closed}</strong>
            </div>

            <div style={{ padding: "var(--space-3)", backgroundColor: "var(--color-bg-card)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)" }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>Rejected Out-of-Scope</span>
              <strong style={{ fontSize: "var(--text-lg)", color: "#991B1B" }}>{metrics.rejected}</strong>
            </div>
          </div>

          {/* Urgent / Immediate Triage Attention Queue */}
          {metrics.urgentComplaints.length > 0 && (
            <div style={{ marginTop: "var(--space-6)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
                <h2 style={{ fontSize: "var(--text-lg)", fontWeight: "var(--weight-bold)", color: "var(--color-tertiary)", display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ color: "#DC2626" }}>●</span> Critical Complaints Requiring Direct Oversight
                </h2>
                <Link to="/admin/complaints?priority=CRITICAL" style={{ fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-primary)", textDecoration: "none" }}>
                  View All Critical &rarr;
                </Link>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {metrics.urgentComplaints.map((comp) => (
                  <div
                    key={comp.id}
                    style={{
                      padding: "var(--space-4)",
                      backgroundColor: "var(--color-bg-card)",
                      border: "1px solid var(--color-border)",
                      borderLeft: "4px solid #DC2626",
                      borderRadius: "var(--radius-sm)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "var(--space-3)",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-primary)", backgroundColor: "var(--color-bg-active-nav)", padding: "2px 6px", borderRadius: 4 }}>
                          {comp.complaint_number}
                        </span>
                        <StatusBadge status={comp.status} />
                        <span style={{ fontSize: "10px", fontWeight: "bold", backgroundColor: "#fee2e2", color: "#991b1b", padding: "2px 6px", borderRadius: 4 }}>
                          {comp.priority || "CRITICAL"}
                        </span>
                        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                          {comp.category_name}
                        </span>
                      </div>
                      <h4 style={{ margin: 0, fontSize: "var(--text-base)", fontWeight: "600", color: "var(--color-text-main)" }}>
                        {comp.title}
                      </h4>
                    </div>

                    <Link to={`/admin/complaints/${comp.id}`}>
                      <Button variant="primary" size="sm">
                        Review Dossier &rarr;
                      </Button>
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Municipal Submissions */}
          <div style={{ marginTop: "var(--space-6)" }}>
            <Card>
              <CardHeader>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
                  <CardTitle>Recent Municipal Submissions Queue</CardTitle>
                  <Link to="/admin/complaints" style={{ fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-primary)", textDecoration: "none" }}>
                    Go to Full Triage Queue &rarr;
                  </Link>
                </div>
              </CardHeader>
              <CardContent>
                {metrics.recentComplaints.length === 0 ? (
                  <EmptyState
                    title="No Complaints on File"
                    description="When citizens file complaints, they will appear here in the operational dispatch queue."
                  />
                ) : (
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--color-border)", textAlign: "left" }}>
                          <th style={{ padding: "10px 12px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Reference</th>
                          <th style={{ padding: "10px 12px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Headline</th>
                          <th style={{ padding: "10px 12px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Category</th>
                          <th style={{ padding: "10px 12px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Priority</th>
                          <th style={{ padding: "10px 12px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Status</th>
                          <th style={{ padding: "10px 12px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Filed Date</th>
                          <th style={{ padding: "10px 12px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.recentComplaints.map((c) => (
                          <tr key={c.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                            <td style={{ padding: "12px", fontFamily: "var(--font-mono)", fontWeight: "bold", color: "var(--color-primary)" }}>
                              {c.complaint_number}
                            </td>
                            <td style={{ padding: "12px", maxWidth: 280, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                              <Link to={`/admin/complaints/${c.id}`} style={{ color: "var(--color-text-main)", textDecoration: "none", fontWeight: "500" }}>
                                {c.title}
                              </Link>
                            </td>
                            <td style={{ padding: "12px", color: "var(--color-text-muted)" }}>
                              {c.category_name || "General"}
                            </td>
                            <td style={{ padding: "12px" }}>
                              <span style={{ fontSize: "10px", fontWeight: "bold", textTransform: "uppercase", padding: "2px 6px", borderRadius: 4, backgroundColor: c.priority === "URGENT" ? "#fee2e2" : c.priority === "HIGH" ? "#ffedd5" : "#f1f5f9", color: c.priority === "URGENT" ? "#991b1b" : c.priority === "HIGH" ? "#9a3412" : "#475569" }}>
                                {c.priority}
                              </span>
                            </td>
                            <td style={{ padding: "12px" }}>
                              <StatusBadge status={c.status} />
                            </td>
                            <td style={{ padding: "12px", color: "var(--color-text-muted)" }}>
                              {formatDate(c.created_at)}
                            </td>
                            <td style={{ padding: "12px" }}>
                              <Link to={`/admin/complaints/${c.id}`}>
                                <Button variant="secondary" size="sm">
                                  Triage &rarr;
                                </Button>
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
};
