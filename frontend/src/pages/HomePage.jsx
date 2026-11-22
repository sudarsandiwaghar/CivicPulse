import React from "react";
import { Link } from "react-router-dom";
import "./HomePage.css";
import { Button } from "../components/Button";
import { useAuth } from "../hooks/useAuth";

export const HomePage = () => {
  const { isAuthenticated, user } = useAuth();

  const getDashboardPath = () => {
    if (!user) return "/login";
    switch (user.role) {
      case "ADMINISTRATOR":
        return "/admin";
      case "FIELD_WORKER":
        return "/worker";
      case "CITIZEN":
      default:
        return "/citizen";
    }
  };

  return (
    <div className="home-page">
      <section className="home-hero">
        <div className="container">
          <div className="home-badge">Modern Municipal Governance</div>
          <h1 className="home-headline">
            Transparent, Accountable &amp; Intelligent <span>Civic Problem Solving</span>
          </h1>
          <p className="home-subhead">
            CivicPulse unifies citizens, municipal administration, and field response teams into
            one real-time platform with dual SLA clocks and full lifecycle visibility.
          </p>

          <div className="home-actions">
            {isAuthenticated ? (
              <Link to={getDashboardPath()}>
                <Button size="lg" variant="primary">
                  Go to {user?.role === "ADMINISTRATOR" ? "Admin Portal" : user?.role === "FIELD_WORKER" ? "Worker Portal" : "Citizen Dashboard"}
                </Button>
              </Link>
            ) : (
              <>
                <Link to="/register">
                  <Button size="lg" variant="primary">
                    Report an Issue
                  </Button>
                </Link>
                <Link to="/login">
                  <Button size="lg" variant="outline">
                    Sign In to Portal
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="home-features container">
        <div className="features-header">
          <h2 className="features-title">Designed for Complete Operational Clarity</h2>
          <p className="features-subtitle">
            Engineered from the ground up with privacy by design, atomic status transitions, and role-based operational portals.
          </p>
        </div>

        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon-wrapper">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </div>
            <h3 className="feature-card-title">Citizen Empowerment</h3>
            <p className="feature-card-desc">
              Submit civic concerns, follow public community remediation efforts, and track unified chronological progress without exposure of personal identifiable information.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <h3 className="feature-card-title">Dual Independent SLA Clocks</h3>
            <p className="feature-card-desc">
              Independent response and resolution timers with automatic pause tracking for on-hold status and deterministic escalation warnings and breach prevention.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
              </svg>
            </div>
            <h3 className="feature-card-title">Field Response Teams</h3>
            <p className="feature-card-desc">
              Dedicated operational task queues for field workers to acknowledge dispatch, record investigation progress milestones, and submit verification-ready resolutions.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
