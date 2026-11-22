import React from "react";
import "./DashboardPages.css";
import { Card, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { useNavigate } from "react-router-dom";

export const CitizenNotificationsPage = () => {
  const navigate = useNavigate();

  return (
    <div className="portal-page" style={{ maxWidth: "680px", margin: "var(--space-8) auto" }}>
      <Card>
        <CardContent>
          <div style={{ textAlign: "center", padding: "var(--space-8) var(--space-4)" }}>
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: "var(--radius-full)",
                backgroundColor: "var(--color-bg-active-nav)",
                color: "var(--color-primary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto var(--space-4)",
              }}
            >
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
            </div>

            <h2 style={{ fontSize: "var(--text-xl)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)", marginBottom: "var(--space-2)" }}>
              Notifications Hub
            </h2>
            <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)", maxWidth: "460px", margin: "0 auto var(--space-6)", lineHeight: "var(--leading-relaxed)" }}>
              Phase 7.2 focuses on citizen complaint submission, tracking, and lifecycle verification. Real-time in-app event notifications (SLA warnings, technician progress notes, and triage updates) will be integrated in a subsequent phase.
            </p>

            <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "center" }}>
              <Button variant="primary" onClick={() => navigate("/citizen")}>
                Return to Dashboard
              </Button>
              <Button variant="outline" onClick={() => navigate("/citizen/complaints")}>
                View My Complaints
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
