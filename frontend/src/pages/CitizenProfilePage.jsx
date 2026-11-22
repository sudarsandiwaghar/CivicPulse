import React from "react";
import "./DashboardPages.css";
import { useAuth } from "../hooks/useAuth";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { useNavigate } from "react-router-dom";

export const CitizenProfilePage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const formatDate = (dateStr) => {
    if (!dateStr) return "N/A";
    try {
      return new Date(dateStr).toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="portal-page" style={{ maxWidth: "680px", margin: "0 auto" }}>
      <div className="portal-header">
        <div>
          <h1 className="portal-header-title">Citizen Account Profile</h1>
          <p className="portal-header-subtitle">
            Your registered credentials and verified municipal identity
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Personal Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", marginBottom: "var(--space-6)" }}>
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
                fontSize: "var(--text-xl)",
                fontWeight: "var(--weight-bold)",
              }}
            >
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : "C"}
            </div>
            <div>
              <h3 style={{ fontSize: "var(--text-lg)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)" }}>
                {user?.full_name}
              </h3>
              <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", marginTop: "4px" }}>
                <span
                  style={{
                    backgroundColor: "var(--color-bg-active-nav)",
                    color: "var(--color-primary)",
                    padding: "2px 8px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "var(--text-xs)",
                    fontWeight: "bold",
                  }}
                >
                  {user?.role}
                </span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-success)" }}>
                  ● Active Verified Account
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", fontSize: "var(--text-sm)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
              <div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                  Full Name
                </span>
                <span style={{ fontWeight: "600", color: "var(--color-text-main)" }}>{user?.full_name}</span>
              </div>
              <div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                  Email Address
                </span>
                <span style={{ fontWeight: "600", color: "var(--color-text-main)" }}>{user?.email}</span>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
              <div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                  Phone Number
                </span>
                <span style={{ color: "var(--color-text-main)" }}>{user?.phone_number || "Not provided"}</span>
              </div>
              <div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block" }}>
                  Member Since
                </span>
                <span style={{ color: "var(--color-text-main)" }}>{formatDate(user?.created_at)}</span>
              </div>
            </div>

            <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-4)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Button variant="outline" onClick={() => navigate("/citizen")}>
                Return to Dashboard
              </Button>
              <Button variant="secondary" onClick={logout}>
                Sign Out
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
