import React from "react";
import { Outlet } from "react-router-dom";
import "./Layouts.css";
import { PublicNavbar } from "../components/PublicNavbar";
import { PublicFooter } from "../components/PublicFooter";

export const PublicLayout = () => {
  return (
    <div className="public-layout-root">
      <PublicNavbar />
      <main className="public-main-content">
        <Outlet />
      </main>
      <PublicFooter />
    </div>
  );
};
