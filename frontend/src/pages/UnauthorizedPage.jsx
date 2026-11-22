import React from "react";
import { Link, useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { useAuth } from "../hooks/useAuth";
import { Card, CardContent } from "../components/Card";
import { Button } from "../components/Button";

export const UnauthorizedPage = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleReturnPortal = () => {
    if (!isAuthenticated || !user) {
      navigate("/login");
      return;
    }

    switch (user.role) {
      case "ADMINISTRATOR":
        navigate("/admin");
        break;
      case "FIELD_WORKER":
        navigate("/worker");
        break;
      case "CITIZEN":
      default:
        navigate("/citizen");
        break;
    }
  };

  return (
    <div className="utility-page-wrapper">
      <div className="utility-card">
        <Card>
          <CardContent>
            <div className="utility-code">403</div>
            <h1 className="utility-title">Access Restricted</h1>
            <p className="utility-desc">
              You do not have the required permissions or role assignment to view this area.
              {user && (
                <span style={{ display: "block", marginTop: "var(--space-2)" }}>
                  Current signed-in role: <strong>{user.role}</strong>
                </span>
              )}
            </p>

            <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "center", flexWrap: "wrap" }}>
              <Button variant="primary" onClick={handleReturnPortal}>
                Return to My Portal
              </Button>
              {isAuthenticated && (
                <Button variant="outline" onClick={logout}>
                  Sign Out
                </Button>
              )}
              {!isAuthenticated && (
                <Link to="/login">
                  <Button variant="secondary">Sign In</Button>
                </Link>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
