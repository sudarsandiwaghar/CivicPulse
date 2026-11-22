import React from "react";
import "./DashboardPages.css";
import { useAuth } from "../hooks/useAuth";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { Button } from "../components/Button";

export const CitizenLandingPage = () => {
  const { user } = useAuth();

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <div className="portal-phase-notice">
            <span>●</span> Citizen Portal Foundation
          </div>
          <h1 className="portal-header-title" style={{ marginTop: "var(--space-2)" }}>
            Welcome back, {user?.full_name || "Citizen"}
          </h1>
          <p className="portal-header-subtitle">
            Track your submitted municipal complaints and view real-time civic updates
          </p>
        </div>
        <div className="portal-header-actions">
          <Button variant="primary">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Report Issue
          </Button>
        </div>
      </div>

      {/* Hero Banner */}
      <div className="portal-banner">
        <div className="portal-banner-content">
          <h2>Civic Engagement at Your Fingertips</h2>
          <p>
            Report neighborhood problems, upload geotagged evidence, and track SLA-backed resolution progress directly with municipal staff.
          </p>
        </div>
        <Button variant="outline" style={{ backgroundColor: "#FFFFFF", color: "var(--color-primary)", borderColor: "#FFFFFF" }}>
          Explore Public Feed
        </Button>
      </div>

      {/* Key Metric Stat Cards */}
      <div className="portal-stats-grid">
        <StatCard
          title="Total Complaints"
          value="0"
          change="All time submissions"
          changeType="neutral"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          }
        />
        <StatCard
          title="Active Resolution"
          value="0"
          change="Currently assigned"
          changeType="neutral"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          }
        />
        <StatCard
          title="Resolved"
          value="0"
          change="Completed successfully"
          changeType="positive"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          }
        />
        <StatCard
          title="Awaiting Verification"
          value="0"
          change="Needs citizen review"
          changeType="neutral"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          }
        />
      </div>

      {/* Main Content Grid */}
      <div className="portal-grid-2col">
        <Card>
          <CardHeader>
            <CardTitle>Recent Complaint Submissions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="portal-empty-state">
              <div className="portal-empty-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </div>
              <h3 style={{ fontSize: "var(--text-base)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-main)", marginBottom: "var(--space-1)" }}>
                No complaints submitted yet
              </h3>
              <p style={{ fontSize: "var(--text-sm)", maxWidth: "360px", margin: "0 auto var(--space-4)" }}>
                When you report issues such as potholes, sanitation, or streetlights, they will appear here with live lifecycle tracking.
              </p>
              <Button variant="secondary" size="sm">
                Submit Your First Issue
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Lifecycle Status Legend</CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>New Submission</span>
                <StatusBadge status="SUBMITTED" />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>Moderation / Triage</span>
                <StatusBadge status="UNDER_REVIEW" />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>Assigned to Crew</span>
                <StatusBadge status="ASSIGNED" />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>Work in Progress</span>
                <StatusBadge status="IN_PROGRESS" />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>Resolved / Verify</span>
                <StatusBadge status="RESOLVED_AWAITING_VERIFICATION" />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>Closed & Verified</span>
                <StatusBadge status="CLOSED" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
