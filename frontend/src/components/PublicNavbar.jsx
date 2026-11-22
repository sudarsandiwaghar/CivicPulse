import React from "react";
import { Link, NavLink } from "react-router-dom";
import "./PublicNavbar.css";
import { useAuth } from "../hooks/useAuth";
import { Button } from "./Button";

export const PublicNavbar = () => {
  const { isAuthenticated, user, logout } = useAuth();

  const getDashboardPath = () => {
    if (!user) return "/";
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
    <header className="public-navbar">
      <div className="container public-navbar-container">
        <Link to="/" className="public-brand-link">
          <div className="public-brand-icon">CP</div>
          <div className="public-brand-name">
            Civic<span>Pulse</span>
          </div>
        </Link>

        <nav className="public-nav-links">
          <NavLink to="/" end className="public-nav-link">
            Home
          </NavLink>
          <NavLink to="/public-feed" className="public-nav-link">
            Public Feed
          </NavLink>

          {isAuthenticated && user ? (
            <>
              <Link to={getDashboardPath()}>
                <Button size="sm" variant="primary">
                  Go to Dashboard
                </Button>
              </Link>
              <Button size="sm" variant="ghost" onClick={logout}>
                Sign Out
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button size="sm" variant="outline">
                  Sign In
                </Button>
              </Link>
              <Link to="/register">
                <Button size="sm" variant="primary">
                  Register
                </Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
};
