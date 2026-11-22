import React, { useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import "./Layouts.css";
import { useAuth } from "../hooks/useAuth";
import { Sidebar } from "../components/Sidebar";
import { TopHeader } from "../components/TopHeader";

export const AuthenticatedLayout = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Derive dynamic page title based on path
  const getPageTitle = () => {
    const path = location.pathname;
    if (path.startsWith("/admin")) return "Administration Portal";
    if (path.startsWith("/worker")) return "Field Worker Operations";
    if (path.startsWith("/citizen")) return "Citizen Portal";
    return "CivicPulse Dashboard";
  };

  return (
    <div className="auth-layout-root">
      <Sidebar
        role={user.role}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="auth-main-wrapper">
        <TopHeader
          pageTitle={getPageTitle()}
          user={user}
          onLogout={logout}
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
        />
        <main className="auth-page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
