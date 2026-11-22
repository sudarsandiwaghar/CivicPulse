import React from "react";
import { Link } from "react-router-dom";
import "./PublicFooter.css";

const CURRENT_YEAR = new Date().getFullYear();

export const PublicFooter = () => {
  return (
    <footer className="public-footer">
      <div className="container footer-container">
        <div className="footer-brand">
          <div className="footer-title">CivicPulse Platform</div>
          <div>Civic Issue Reporting, Monitoring &amp; Intelligence</div>
        </div>
        <div className="footer-links">
          <span>&copy; {CURRENT_YEAR} CivicPulse. All rights reserved.</span>
          <Link to="/public-feed" style={{ color: "var(--color-primary)", marginLeft: "var(--space-3)" }}>
            Public Feed
          </Link>
        </div>
      </div>
    </footer>
  );
};
