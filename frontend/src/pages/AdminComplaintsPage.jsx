import React, { useState, useEffect, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import "./DashboardPages.css";
import { adminService } from "../services/adminService";
import { categoryService } from "../services/categoryService";
import { ApiError } from "../types/api";
import { Card, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";
import { StatusBadge } from "../components/StatusBadge";

const STATUS_TABS = [
  { label: "All Complaints", value: "ALL" },
  { label: "Pending Triage", value: "SUBMITTED" },
  { label: "Under Review", value: "UNDER_REVIEW" },
  { label: "Dispatched (Assigned)", value: "ASSIGNED" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Awaiting Verification", value: "RESOLVED_AWAITING_VERIFICATION" },
  { label: "Closed & Resolved", value: "CLOSED" },
  { label: "Rejected / Duplicate", value: "ARCHIVED" },
];

const PRIORITY_OPTIONS = [
  { label: "All Priorities", value: "" },
  { label: "Urgent", value: "URGENT" },
  { label: "High", value: "HIGH" },
  { label: "Medium", value: "MEDIUM" },
  { label: "Low", value: "LOW" },
];

function formatDate(dateStr) {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export const AdminComplaintsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const initialTab = searchParams.get("tab") || "ALL";
  const initialPriority = searchParams.get("priority") || "";

  const [activeTab, setActiveTab] = useState(initialTab);
  const [categories, setCategories] = useState([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedPriority, setSelectedPriority] = useState(initialPriority);
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const [complaints, setComplaints] = useState([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load categories once
  useEffect(() => {
    categoryService.getCategories().then(setCategories).catch(() => {});
  }, []);

  const fetchComplaints = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const filters = {
        page,
        page_size: pageSize,
        sort_by: "created_at",
        sort_order: "desc",
      };

      if (activeTab !== "ALL" && activeTab !== "ARCHIVED") {
        filters.status = activeTab;
      }
      if (selectedPriority) {
        filters.priority = selectedPriority;
      }
      if (selectedCategoryId) {
        filters.category_id = selectedCategoryId;
      }
      if (searchQuery.trim()) {
        filters.search = searchQuery.trim();
      }

      const res = await adminService.listComplaints(filters);
      let items = res.data || [];

      // If ARCHIVED tab selected, filter for REJECTED or DUPLICATE
      if (activeTab === "ARCHIVED") {
        items = items.filter((c) => c.status === "REJECTED" || c.status === "DUPLICATE");
      }

      setComplaints(items);
      setTotalItems(res.total_items || 0);
      setTotalPages(res.total_pages || 1);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || "Failed to load complaints queue.");
      } else {
        setError("Network error. Please verify your connection.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, activeTab, selectedPriority, selectedCategoryId, searchQuery]);

  useEffect(() => {
    fetchComplaints();
  }, [fetchComplaints]);

  const handleTabChange = (tabValue) => {
    setActiveTab(tabValue);
    setPage(1);
    const newParams = new URLSearchParams(searchParams);
    if (tabValue !== "ALL") {
      newParams.set("tab", tabValue);
    } else {
      newParams.delete("tab");
    }
    setSearchParams(newParams);
  };

  const handleClearFilters = () => {
    setActiveTab("ALL");
    setSelectedPriority("");
    setSelectedCategoryId("");
    setSearchQuery("");
    setPage(1);
    setSearchParams({});
  };

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <div className="portal-phase-notice">
            <span>●</span> Administrator Command Portal
          </div>
          <h1 className="portal-header-title" style={{ marginTop: "var(--space-2)" }}>
            Municipal Complaint Triage Queue
          </h1>
          <p className="portal-header-subtitle">
            Review incoming citizen reports, perform triage, adjust operational priority, and dispatch to field crews
          </p>
        </div>
        <div className="portal-header-actions">
          <Link to="/admin">
            <Button variant="secondary">
              &larr; Operations Center
            </Button>
          </Link>
        </div>
      </div>

      {/* Status Filter Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--color-border)",
          gap: "var(--space-2)",
          marginBottom: "var(--space-4)",
          overflowX: "auto",
        }}
      >
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => handleTabChange(tab.value)}
            style={{
              padding: "var(--space-3) var(--space-4)",
              background: "none",
              border: "none",
              borderBottom: activeTab === tab.value ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: activeTab === tab.value ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: activeTab === tab.value ? "var(--weight-bold)" : "var(--weight-medium)",
              cursor: "pointer",
              fontSize: "var(--text-sm)",
              whiteSpace: "nowrap",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Filter and Search Bar */}
      <Card style={{ marginBottom: "var(--space-4)" }}>
        <CardContent>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "var(--space-3)",
            }}
          >
            {/* Search Input */}
            <div style={{ flex: "1 1 240px" }}>
              <input
                type="text"
                placeholder="Search reference, headline, or locality..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--color-border)",
                  fontSize: "var(--text-sm)",
                  color: "var(--color-text-main)",
                }}
              />
            </div>

            {/* Category Filter */}
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <label style={{ fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-muted)", textTransform: "uppercase" }}>
                Category:
              </label>
              <select
                value={selectedCategoryId}
                onChange={(e) => {
                  setSelectedCategoryId(e.target.value);
                  setPage(1);
                }}
                style={{
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--color-border)",
                  fontSize: "var(--text-sm)",
                  backgroundColor: "#fff",
                }}
              >
                <option value="">All Categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Priority Filter */}
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <label style={{ fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-muted)", textTransform: "uppercase" }}>
                Priority:
              </label>
              <select
                value={selectedPriority}
                onChange={(e) => {
                  setSelectedPriority(e.target.value);
                  setPage(1);
                }}
                style={{
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--color-border)",
                  fontSize: "var(--text-sm)",
                  backgroundColor: "#fff",
                }}
              >
                {PRIORITY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {(selectedPriority || selectedCategoryId || searchQuery || activeTab !== "ALL") && (
              <Button variant="outline" size="sm" onClick={handleClearFilters}>
                Clear Filters
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Error state */}
      {error && (
        <Alert variant="error" title="Queue Error">
          {error}
          <div style={{ marginTop: "var(--space-2)" }}>
            <Button variant="outline" size="sm" onClick={fetchComplaints}>
              Retry Loading Queue
            </Button>
          </div>
        </Alert>
      )}

      {/* Loading state */}
      {isLoading && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "var(--space-8)", minHeight: "40vh" }}>
          <Spinner size="lg" />
          <span style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
            Retrieving complaint triage records...
          </span>
        </div>
      )}

      {/* Complaints Table */}
      {!isLoading && !error && (
        <>
          {complaints.length === 0 ? (
            <Card>
              <CardContent>
                <EmptyState
                  title="No Complaints Found"
                  description="No complaint records match your current filter parameters."
                  action={
                    <Button variant="secondary" size="sm" onClick={handleClearFilters}>
                      Reset Filters
                    </Button>
                  }
                />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent style={{ padding: 0 }}>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--color-border)", backgroundColor: "var(--color-bg-subtle)", textAlign: "left" }}>
                        <th style={{ padding: "12px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Reference</th>
                        <th style={{ padding: "12px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Complaint Details</th>
                        <th style={{ padding: "12px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Category</th>
                        <th style={{ padding: "12px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Priority</th>
                        <th style={{ padding: "12px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Status</th>
                        <th style={{ padding: "12px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Locality</th>
                        <th style={{ padding: "12px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Filed Date</th>
                        <th style={{ padding: "12px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", textTransform: "uppercase" }}>Triage Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {complaints.map((c) => {
                        const locationText = c.location
                          ? [c.location.ward_or_district, c.location.city].filter(Boolean).join(", ")
                          : "General Area";

                        return (
                          <tr key={c.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                            <td style={{ padding: "14px 16px", fontFamily: "var(--font-mono)", fontWeight: "bold", color: "var(--color-primary)", whiteSpace: "nowrap" }}>
                              {c.complaint_number}
                            </td>
                            <td style={{ padding: "14px 16px", maxWidth: 300 }}>
                              <Link to={`/admin/complaints/${c.id}`} style={{ fontWeight: "600", color: "var(--color-text-main)", textDecoration: "none", display: "block" }}>
                                {c.title}
                              </Link>
                              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "block", marginTop: 2 }}>
                                Citizen: {c.citizen_name || "Confidential"}
                              </span>
                            </td>
                            <td style={{ padding: "14px 16px", color: "var(--color-text-body)", whiteSpace: "nowrap" }}>
                              {c.category_name || "General"}
                            </td>
                            <td style={{ padding: "14px 16px" }}>
                              <span style={{ fontSize: "10px", fontWeight: "bold", padding: "2px 6px", borderRadius: 4, textTransform: "uppercase", backgroundColor: c.priority === "URGENT" ? "#fee2e2" : c.priority === "HIGH" ? "#ffedd5" : "#f1f5f9", color: c.priority === "URGENT" ? "#991b1b" : c.priority === "HIGH" ? "#9a3412" : "#475569" }}>
                                {c.priority}
                              </span>
                            </td>
                            <td style={{ padding: "14px 16px" }}>
                              <StatusBadge status={c.status} />
                            </td>
                            <td style={{ padding: "14px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)" }}>
                              {locationText}
                            </td>
                            <td style={{ padding: "14px 16px", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", whiteSpace: "nowrap" }}>
                              {formatDate(c.created_at)}
                            </td>
                            <td style={{ padding: "14px 16px", whiteSpace: "nowrap" }}>
                              <Link to={`/admin/complaints/${c.id}`}>
                                <Button variant={c.status === "SUBMITTED" ? "primary" : "secondary"} size="sm">
                                  {c.status === "SUBMITTED" ? "Triage Now" : "Manage"} &rarr;
                                </Button>
                              </Link>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div style={{ padding: "var(--space-4)" }}>
                  <Pagination
                    currentPage={page}
                    totalPages={totalPages}
                    totalItems={totalItems}
                    pageSize={pageSize}
                    onPageChange={(p) => setPage(p)}
                  />
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
};
