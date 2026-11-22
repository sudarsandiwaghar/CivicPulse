import React, { useEffect, useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { useAuth } from "../hooks/useAuth";
import { citizenService } from "../services/citizenService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { StatCard } from "../components/StatCard";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { Spinner } from "../components/Spinner";
import { EmptyState } from "../components/EmptyState";
import { ComplaintCard } from "../components/ComplaintCard";

export const CitizenDashboardPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("submissions");

  const fetchDashboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await citizenService.getDashboard();
      setData(result);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load citizen dashboard. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (isLoading && !data) {
    return (
      <div className="portal-page" style={{ alignItems: "center", justifyContent: "center", minHeight: "50vh" }}>
        <Spinner size="lg" />
        <span style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)" }}>
          Loading your civic reporting metrics...
        </span>
      </div>
    );
  }

  const metrics = data?.metrics;

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <h1 className="portal-header-title">
            Welcome back, {user?.full_name || "Citizen"}
          </h1>
          <p className="portal-header-subtitle">
            Monitor real-time updates and lifecycle status for your municipal reports
          </p>
        </div>
        <div className="portal-header-actions">
          <Button variant="outline" size="sm" onClick={fetchDashboard} disabled={isLoading}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            Refresh Data
          </Button>
          <Button variant="primary" size="sm" onClick={() => navigate("/citizen/report")}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Report Issue
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Connection Notice">
          {error}
        </Alert>
      )}

      {/* Hero Banner */}
      <div className="portal-banner">
        <div className="portal-banner-content">
          <h2>Active Civic Community</h2>
          <p>
            Report municipal concerns directly to local authorities. Track technician assignments, on-site milestones, and SLA deadlines.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => navigate("/citizen/report")}
          style={{ backgroundColor: "#FFFFFF", color: "var(--color-primary)", borderColor: "#FFFFFF", whiteSpace: "nowrap" }}
        >
          Submit New Complaint
        </Button>
      </div>

      {/* Live Backend Stat Cards */}
      <div className="portal-stats-grid">
        <StatCard
          label="Total Filed"
          value={metrics?.total_complaints ?? 0}
          subtitle="All time submissions"
          changeType="neutral"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          }
        />
        <StatCard
          label="Active Resolution"
          value={metrics?.active_complaints ?? 0}
          subtitle="Assigned or in progress"
          changeType="neutral"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          }
        />
        <StatCard
          label="Awaiting Verification"
          value={metrics?.awaiting_verification ?? 0}
          subtitle="Action required by you"
          changeType={metrics && metrics.awaiting_verification > 0 ? "negative" : "neutral"}
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          }
        />
        <StatCard
          label="Verified Closed"
          value={metrics?.closed_complaints ?? 0}
          subtitle="Completed resolutions"
          changeType="positive"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          }
        />
      </div>

      {/* Action Required Callout Section */}
      {data?.action_required && data.action_required.length > 0 && (
        <Card style={{ borderColor: "var(--color-secondary)", backgroundColor: "#FCFEFE" }}>
          <CardHeader>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <span style={{ color: "var(--color-primary)", fontWeight: "bold" }}>● Action Required</span>
                <CardTitle>Awaiting Citizen Verification ({data.action_required.length})</CardTitle>
              </div>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                Technician marked resolved — Please review on-site results
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "var(--space-3)" }}>
              {data.action_required.map((comp) => (
                <ComplaintCard
                  key={comp.id}
                  id={comp.id}
                  complaintNumber={comp.complaint_number}
                  title={comp.title}
                  categoryName={comp.category_name}
                  status={comp.status}
                  priority={comp.priority}
                  createdAt={comp.created_at}
                  showActionNotice
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Activity Feeds */}
      <div className="portal-grid-2col">
        <Card>
          <CardHeader>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
              <CardTitle>Recent Activity</CardTitle>
              <div style={{ display: "flex", gap: "var(--space-1)" }}>
                <Button
                  size="sm"
                  variant={activeTab === "submissions" ? "primary" : "ghost"}
                  onClick={() => setActiveTab("submissions")}
                >
                  Recent Submissions
                </Button>
                <Button
                  size="sm"
                  variant={activeTab === "updates" ? "primary" : "ghost"}
                  onClick={() => setActiveTab("updates")}
                >
                  Recent Updates
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {activeTab === "submissions" ? (
              data?.recent_submissions && data.recent_submissions.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                  {data.recent_submissions.map((comp) => (
                    <ComplaintCard
                      key={comp.id}
                      id={comp.id}
                      complaintNumber={comp.complaint_number}
                      title={comp.title}
                      categoryName={comp.category_name}
                      status={comp.status}
                      priority={comp.priority}
                      createdAt={comp.created_at}
                    />
                  ))}
                  <div style={{ textAlign: "center", marginTop: "var(--space-2)" }}>
                    <Link to="/citizen/complaints" style={{ fontSize: "var(--text-sm)", fontWeight: "bold" }}>
                      View All Submitted Complaints →
                    </Link>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="No submissions recorded yet"
                  description="When you file a report about roads, sanitation, or lighting, your tracking status will appear here."
                  actionText="Report First Issue"
                  onAction={() => navigate("/citizen/report")}
                />
              )
            ) : data?.recent_updates && data.recent_updates.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {data.recent_updates.map((comp) => (
                  <ComplaintCard
                    key={comp.id}
                    id={comp.id}
                    complaintNumber={comp.complaint_number}
                    title={comp.title}
                    categoryName={comp.category_name}
                    status={comp.status}
                    priority={comp.priority}
                    createdAt={comp.created_at}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No recent updates"
                description="Status transitions and worker milestones will be reflected here in real time."
              />
            )}
          </CardContent>
        </Card>

        {/* Quick Links & Information */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <Card>
            <CardHeader>
              <CardTitle>Citizen Shortcuts</CardTitle>
            </CardHeader>
            <CardContent>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                <Button
                  variant="outline"
                  fullWidth
                  onClick={() => navigate("/citizen/report")}
                  style={{ justifyContent: "flex-start" }}
                >
                  <span style={{ marginRight: "var(--space-2)" }}>📝</span> Report a New Issue
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  onClick={() => navigate("/citizen/complaints")}
                  style={{ justifyContent: "flex-start" }}
                >
                  <span style={{ marginRight: "var(--space-2)" }}>📋</span> View My Complaints List
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  onClick={() => navigate("/citizen/track")}
                  style={{ justifyContent: "flex-start" }}
                >
                  <span style={{ marginRight: "var(--space-2)" }}>🔍</span> Track by Reference Code
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  onClick={() => navigate("/citizen/profile")}
                  style={{ justifyContent: "flex-start" }}
                >
                  <span style={{ marginRight: "var(--space-2)" }}>👤</span> My Account Profile
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Municipal SLA Promise</CardTitle>
            </CardHeader>
            <CardContent>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", lineHeight: "var(--leading-relaxed)" }}>
                <p style={{ marginBottom: "var(--space-2)" }}>
                  CivicPulse holds municipal departments accountable via dual independent response and resolution clocks.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <span style={{ color: "var(--color-primary)", fontWeight: "bold" }}>●</span>
                    <span><strong>Response Clock:</strong> Measured until field technician assignment.</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <span style={{ color: "var(--color-primary)", fontWeight: "bold" }}>●</span>
                    <span><strong>Resolution Clock:</strong> Concludes when work is completed for verification.</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
