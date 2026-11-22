import React from "react";
import { Link } from "react-router-dom";
import "./DashboardPages.css";
import { Card, CardContent } from "../components/Card";
import { Button } from "../components/Button";

export const NotFoundPage = () => {
  return (
    <div className="utility-page-wrapper">
      <div className="utility-card">
        <Card>
          <CardContent>
            <div className="utility-code">404</div>
            <h1 className="utility-title">Page Not Found</h1>
            <p className="utility-desc">
              The municipal portal route or resource you are trying to reach does not exist or has been relocated.
            </p>

            <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "center" }}>
              <Link to="/">
                <Button variant="primary">Return to Home</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
