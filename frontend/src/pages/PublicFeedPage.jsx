import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import "./DashboardPages.css";
import { publicComplaintService } from "../services/publicComplaintService";
import { categoryService } from "../services/categoryService";
import { ApiError } from "../types/api";
import { Card, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Pagination } from "../components/Pagination";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { PublicComplaintCard } from "../components/PublicComplaintCard";

const PUBLIC_STATUS_OPTIONS = [
  { label: "All Statuses", value: "" },
  { label: "Under Review", value: "UNDER_REVIEW" },
  { label: "Assigned", value: "ASSIGNED" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Resolved (Awaiting Verification)", value: "RESOLVED_AWAITING_VERIFICATION" },
  { label: "Closed & Verified", value: "CLOSED" },
];

export const PublicFeedPage = () => {
  const [complaints, setComplaints] = useState([]);
  const [categories, setCategories] = useState([]);

  // Filter States
  const [categoryId, setCategoryId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(12);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  // Loading & Error States
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load Categories on mount
  useEffect(() => {
    const loadCategories = async () => {
      try {
        const catList = await categoryService.getActiveCategories();
        setCategories(catList);
      } catch {
        // Soft fail; categories dropdown can remain with 'All Categories'
      }
    };
    loadCategories();
  }, []);

  const fetchFeed = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await publicComplaintService.getPublicFeed({
        category_id: categoryId ? parseInt(categoryId, 10) : undefined,
        status: statusFilter ? statusFilter : undefined,
        page,
        page_size: pageSize,
      });

      setComplaints(res.items);
      setTotalPages(res.total_pages);
      setTotalItems(res.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to load public complaints feed. Please check your connection.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [categoryId, statusFilter, page, pageSize]);

  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  const handleCategoryChange = (val) => {
    setCategoryId(val);
    setPage(1);
  };

  const handleStatusChange = (val) => {
    setStatusFilter(val);
    setPage(1);
  };

  const handleResetFilters = () => {
    setCategoryId("");
    setStatusFilter("");
    setPage(1);
  };

  return (
    <div className="container" style={{ padding: "var(--space-8) var(--space-4)" }}>
      {/* Hero Header */}
      <div style={{ textAlign: "center", marginBottom: "var(--space-8)" }}>
        <div className="portal-phase-notice" style={{ marginBottom: "var(--space-3)" }}>
          <span>●</span> Public Community Bulletin
        </div>
        <h1 style={{ fontSize: "var(--text-3xl)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)", marginBottom: "var(--space-2)" }}>
          Civic Transparency Feed
        </h1>
        <p style={{ fontSize: "var(--text-base)", color: "var(--color-text-muted)", maxWidth: "600px", margin: "0 auto" }}>
          Browse verified municipal issues published by local authorities. Follow neighborhood updates to track on-site resolution progress in real time.
        </p>
      </div>

      {error && (
        <div style={{ marginBottom: "var(--space-6)" }}>
          <Alert variant="error" title="Feed Retrieval Notice">
            {error}
          </Alert>
          <div style={{ marginTop: "var(--space-3)", textAlign: "center" }}>
            <Button variant="outline" size="sm" onClick={fetchFeed}>
              Retry Loading Feed
            </Button>
          </div>
        </div>
      )}

      {/* Filter Toolbar */}
      <Card style={{ marginBottom: "var(--space-6)" }}>
        <CardContent>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-4)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", flexWrap: "wrap" }}>
              {/* Category Filter */}
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <label style={{ fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-main)" }}>
                  Category:
                </label>
                <select
                  value={categoryId}
                  onChange={(e) => handleCategoryChange(e.target.value)}
                  style={{
                    padding: "8px 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-bg-card)",
                    fontSize: "var(--text-sm)",
                    color: "var(--color-text-main)",
                    outline: "none",
                  }}
                >
                  <option value="">All Categories</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id.toString()}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Status Filter */}
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <label style={{ fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-main)" }}>
                  Status:
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  style={{
                    padding: "8px 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-bg-card)",
                    fontSize: "var(--text-sm)",
                    color: "var(--color-text-main)",
                    outline: "none",
                  }}
                >
                  {PUBLIC_STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {(categoryId || statusFilter) && (
                <Button variant="ghost" size="sm" onClick={handleResetFilters}>
                  Clear Filters
                </Button>
              )}
            </div>

            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {totalItems} published {totalItems === 1 ? "issue" : "issues"} available
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Complaint Grid */}
      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "var(--space-16) 0" }}>
          <Spinner size="lg" />
          <span style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
            Loading published municipal issues...
          </span>
        </div>
      ) : complaints.length === 0 ? (
        <EmptyState
          title={categoryId || statusFilter ? "No matching public complaints" : "No public complaints published yet"}
          description={
            categoryId || statusFilter
              ? "No civic complaints match your active filter selection. Try selecting all categories or statuses."
              : "Municipal authorities have not published any complaints to the community feed at this time."
          }
          actionText={categoryId || statusFilter ? "Reset Filters" : undefined}
          onAction={categoryId || statusFilter ? handleResetFilters : undefined}
        />
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "var(--space-5)" }}>
            {complaints.map((c) => (
              <PublicComplaintCard key={c.id} complaint={c} />
            ))}
          </div>

          {totalPages > 1 && (
            <div style={{ marginTop: "var(--space-8)" }}>
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                onPageChange={(newPage) => setPage(newPage)}
              />
            </div>
          )}
        </>
      )}

      {/* Community Call to Action Footer */}
      <div style={{ marginTop: "var(--space-12)", textAlign: "center", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-8)" }}>
        <h3 style={{ fontSize: "var(--text-lg)", fontWeight: "bold", color: "var(--color-text-main)", marginBottom: "var(--space-2)" }}>
          Notice a neighborhood problem that isn't listed?
        </h3>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)", maxWidth: "500px", margin: "0 auto var(--space-4)" }}>
          Registered citizens can report municipal potholes, streetlights, water supply disruptions, and sanitation issues directly.
        </p>
        <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "center" }}>
          <Link to="/register">
            <Button variant="primary">Register as Citizen</Button>
          </Link>
          <Link to="/login">
            <Button variant="outline">Sign In to Account</Button>
          </Link>
        </div>
      </div>
    </div>
  );
};
