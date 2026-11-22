import React, { Suspense, lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { PublicLayout } from "../layouts/PublicLayout";
import { AuthenticatedLayout } from "../layouts/AuthenticatedLayout";
import { ProtectedRoute } from "./ProtectedRoute";
import { Spinner } from "../components/Spinner";

const PageLoader = () => (
  <div
    style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      minHeight: "50vh",
    }}
  >
    <Spinner size="md" />
  </div>
);

// Robust lazy loader handling both named and default exports
const lazyPage = (importFn, name) =>
  lazy(async () => {
    const mod = await importFn();
    return { default: mod[name] || mod.default };
  });

// Public pages
const HomePage = lazyPage(() => import("../pages/HomePage"), "HomePage");
const LoginPage = lazyPage(() => import("../pages/LoginPage"), "LoginPage");
const RegisterPage = lazyPage(() => import("../pages/RegisterPage"), "RegisterPage");
const PublicFeedPage = lazyPage(() => import("../pages/PublicFeedPage"), "PublicFeedPage");
const PublicComplaintDetailPage = lazyPage(
  () => import("../pages/PublicComplaintDetailPage"),
  "PublicComplaintDetailPage"
);
const UnauthorizedPage = lazyPage(() => import("../pages/UnauthorizedPage"), "UnauthorizedPage");
const NotFoundPage = lazyPage(() => import("../pages/NotFoundPage"), "NotFoundPage");

// Shared authenticated pages
const NotificationsPage = lazyPage(() => import("../pages/NotificationsPage"), "NotificationsPage");

// Citizen pages
const CitizenDashboardPage = lazyPage(() => import("../pages/CitizenDashboardPage"), "CitizenDashboardPage");
const CitizenComplaintsPage = lazyPage(() => import("../pages/CitizenComplaintsPage"), "CitizenComplaintsPage");
const CitizenReportPage = lazyPage(() => import("../pages/CitizenReportPage"), "CitizenReportPage");
const CitizenComplaintDetailPage = lazyPage(
  () => import("../pages/CitizenComplaintDetailPage"),
  "CitizenComplaintDetailPage"
);
const CitizenTrackPage = lazyPage(() => import("../pages/CitizenTrackPage"), "CitizenTrackPage");
const CitizenFollowingPage = lazyPage(() => import("../pages/CitizenFollowingPage"), "CitizenFollowingPage");
const CitizenProfilePage = lazyPage(() => import("../pages/CitizenProfilePage"), "CitizenProfilePage");
const CitizenComplaintMapPage = lazyPage(
  () => import("../pages/CitizenComplaintMapPage"),
  "CitizenComplaintMapPage"
);

// Administrator pages
const AdminDashboardPage = lazyPage(() => import("../pages/AdminDashboardPage"), "AdminDashboardPage");
const AdminComplaintsPage = lazyPage(() => import("../pages/AdminComplaintsPage"), "AdminComplaintsPage");
const AdminComplaintDetailPage = lazyPage(
  () => import("../pages/AdminComplaintDetailPage"),
  "AdminComplaintDetailPage"
);
const AdminComplaintMapPage = lazyPage(
  () => import("../pages/AdminComplaintMapPage"),
  "AdminComplaintMapPage"
);
const AdminWorkersPage = lazyPage(() => import("../pages/AdminWorkersPage"), "AdminWorkersPage");
const AdminDepartmentsPage = lazyPage(() => import("../pages/AdminDepartmentsPage"), "AdminDepartmentsPage");
const AdminModerationPage = lazyPage(() => import("../pages/AdminModerationPage"), "AdminModerationPage");
const AdminSLADashboardPage = lazyPage(
  () => import("../pages/AdminSLADashboardPage"),
  "AdminSLADashboardPage"
);
const AdminSLAPoliciesPage = lazyPage(
  () => import("../pages/AdminSLAPoliciesPage"),
  "AdminSLAPoliciesPage"
);

// Field worker pages
const WorkerDashboardPage = lazyPage(() => import("../pages/WorkerDashboardPage"), "WorkerDashboardPage");
const WorkerTasksPage = lazyPage(() => import("../pages/WorkerTasksPage"), "WorkerTasksPage");
const WorkerTaskDetailPage = lazyPage(
  () => import("../pages/WorkerTaskDetailPage"),
  "WorkerTaskDetailPage"
);

export const AppRoutes = () => {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Public Pages wrapped in PublicLayout */}
        <Route element={<PublicLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/public-feed" element={<PublicFeedPage />} />
          <Route path="/public-feed/:id" element={<PublicComplaintDetailPage />} />
          <Route path="/unauthorized" element={<UnauthorizedPage />} />
        </Route>

        {/* Authenticated Dashboard Pages wrapped in AuthenticatedLayout */}
        <Route element={<AuthenticatedLayout />}>
          {/* Shared Authenticated Notifications Route */}
          <Route element={<ProtectedRoute allowedRoles={["CITIZEN", "FIELD_WORKER", "ADMINISTRATOR"]} />}>
            <Route path="/notifications" element={<NotificationsPage />} />
          </Route>

          {/* Citizen Portal */}
          <Route element={<ProtectedRoute allowedRoles={["CITIZEN"]} />}>
            <Route path="/citizen" element={<CitizenDashboardPage />} />
            <Route path="/citizen/complaints" element={<CitizenComplaintsPage />} />
            <Route path="/citizen/map" element={<CitizenComplaintMapPage />} />
            <Route path="/citizen/complaints/:id" element={<CitizenComplaintDetailPage />} />
            <Route path="/citizen/report" element={<CitizenReportPage />} />
            <Route path="/citizen/following" element={<CitizenFollowingPage />} />
            <Route path="/citizen/track" element={<CitizenTrackPage />} />
            <Route path="/citizen/track/:id" element={<CitizenComplaintDetailPage />} />
            <Route path="/citizen/notifications" element={<Navigate to="/notifications" replace />} />
            <Route path="/citizen/profile" element={<CitizenProfilePage />} />
          </Route>

          {/* Field Worker Portal */}
          <Route element={<ProtectedRoute allowedRoles={["FIELD_WORKER"]} />}>
            <Route path="/worker" element={<WorkerDashboardPage />} />
            <Route path="/worker/tasks" element={<WorkerTasksPage />} />
            <Route path="/worker/tasks/in-progress" element={<WorkerTasksPage initialStatusFilter="IN_PROGRESS" />} />
            <Route path="/worker/tasks/completed" element={<WorkerTasksPage initialStatusFilter="COMPLETED" />} />
            <Route path="/worker/tasks/:assignmentId" element={<WorkerTaskDetailPage />} />
            <Route path="/worker/active" element={<Navigate to="/worker/tasks/in-progress" replace />} />
            <Route path="/worker/history" element={<Navigate to="/worker/tasks/completed" replace />} />
          </Route>

          {/* Administrator Portal */}
          <Route element={<ProtectedRoute allowedRoles={["ADMINISTRATOR"]} />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route path="/admin/complaints" element={<AdminComplaintsPage />} />
            <Route path="/admin/complaints/:id" element={<AdminComplaintDetailPage />} />
            <Route path="/admin/map" element={<AdminComplaintMapPage />} />
            <Route path="/admin/workers" element={<AdminWorkersPage />} />
            <Route path="/admin/departments" element={<AdminDepartmentsPage />} />
            <Route path="/admin/moderation" element={<AdminModerationPage />} />
            <Route path="/admin/sla" element={<AdminSLADashboardPage />} />
            <Route path="/admin/sla/policies" element={<AdminSLAPoliciesPage />} />
          </Route>
        </Route>

        {/* Catch-all 404 Route wrapped in PublicLayout */}
        <Route element={<PublicLayout />}>
          <Route path="/404" element={<NotFoundPage />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
};

export default AppRoutes;
