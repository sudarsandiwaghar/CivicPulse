import React, { useEffect, useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { complaintService } from "../services/complaintService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { StatusBadge } from "../components/StatusBadge";
import { Pagination } from "../components/Pagination";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";

const STATUS_OPTIONS = [
  { label: "All Statuses", value: "" },
  { label: "Submitted", value: "SUBMITTED" },
  { label: "Under Review", value: "UNDER_REVIEW" },
  { label: "Assigned", value: "ASSIGNED" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Awaiting Verification", value: "RESOLVED_AWAITING_VERIFICATION" },
  { label: "Closed & Verified", value: "CLOSED" },
  { label: "Rejected", value: "REJECTED" },
  { label: "On Hold", value: "ON_HOLD" },
  { label: "Reopened", value: "REOPENED" },
];

const PRIORITY_OPTIONS = [
  { label: "All Priorities", value: "" },
  { label: "Critical", value: "CRITICAL" },
  { label: "High", value: "HIGH" },
  { label: "Medium", value: "MEDIUM" },
  { label: "Low", value: "LOW" },
];

export const CitizenComplaintsPage = () => {
  const navigate = useNavigate();

  const [complaints, setComplaints] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchComplaints = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await complaintService.listComplaints({
        page,
        page_size: pageSize,
        status: statusFilter ? statusFilter : undefined,
        priority: priorityFilter ? priorityFilter : undefined,
        search: appliedSearch ? appliedSearch.trim() : undefined,
        sort_by: "created_at",
        sort_order: "desc",
      });

      setComplaints(res.data);
      setTotalPages(res.total_pages);
      setTotalItems(res.total_items);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to retrieve complaints. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, statusFilter, priorityFilter, appliedSearch]);

  useEffect(() => {
    fetchComplaints();
  }, [fetchComplaints]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    setAppliedSearch(searchTerm);
  };

  const handleStatusChange = (val) => {
    setStatusFilter(val);
    setPage(1);
  };

  const handlePriorityChange = (val) => {
    setPriorityFilter(val);
    setPage(1);
  };

  const formatDate = (dateStr) => {
    try {
      return new Date(dateStr).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <h1 className="portal-header-title">My Filed Complaints</h1>
          <p className="portal-header-subtitle">
            View, filter, and track all municipal complaints you have submitted
          </p>
        </div>
        <div className="portal-header-actions">
          <Button variant="primary" size="sm" onClick={() => navigate("/citizen/report")}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            File New Complaint
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Data Retrieval Error">
          {error}
        </Alert>
      )}

      {/* Filter and Search Bar Card */}
      <Card>
        <CardContent>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-4)", alignItems: "center", justifyContent: "space-between" }}>
            <form onSubmit={handleSearchSubmit} style={{ display: "flex", gap: "var(--space-2)", flex: "1 1 300px" }}>
              <div style={{ flex: 1 }}>
                <Input
                  type="text"
                  placeholder="Search by tracking code, title, or keywords..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <Button type="submit" variant="secondary">
                Search
              </Button>
              {appliedSearch && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setSearchTerm("");
                    setAppliedSearch("");
                    setPage(1);
                  }}
                >
                  Clear
                </Button>
              )}
            </form>

            <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "center" }}>
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
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <label style={{ fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-main)" }}>
                  Priority:
                </label>
                <select
                  value={priorityFilter}
                  onChange={(e) => handlePriorityChange(e.target.value)}
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
                  {PRIORITY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Table / List Content Card */}
      <Card>
        <CardHeader>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
            <CardTitle>
              My Complaints {totalItems > 0 && <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>({totalItems} records found)</span>}
            </CardTitle>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              Page {page} of {totalPages || 1}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", padding: "var(--space-12) 0" }}>
              <Spinner size="md" />
              <span style={{ marginLeft: "var(--space-3)", color: "var(--color-text-muted)" }}>
                Loading complaints...
              </span>
            </div>
          ) : complaints.length === 0 ? (
            <EmptyState
              title={appliedSearch || statusFilter ? "No matching complaints found" : "No complaints submitted yet"}
              description={
                appliedSearch || statusFilter
                  ? "Try resetting your search query or status filter to see all your records."
                  : "You haven't reported any civic issues yet. Click below to submit your first report."
              }
              actionText={appliedSearch || statusFilter ? "Clear Filters" : "Submit Issue"}
              onAction={() => {
                if (appliedSearch || statusFilter) {
                  setSearchTerm("");
                  setAppliedSearch("");
                  setStatusFilter("");
                  setPriorityFilter("");
                  setPage(1);
                } else {
                  navigate("/citizen/report");
                }
              }}
            />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid var(--color-border)", backgroundColor: "var(--color-bg-app)" }}>
                    <th style={{ padding: "12px 16px", fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-muted)", textTransform: "uppercase" }}>
                      Reference Code
                    </th>
                    <th style={{ padding: "12px 16px", fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-muted)", textTransform: "uppercase" }}>
                      Issue Title
                    </th>
                    <th style={{ padding: "12px 16px", fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-muted)", textTransform: "uppercase" }}>
                      Category
                    </th>
                    <th style={{ padding: "12px 16px", fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-muted)", textTransform: "uppercase" }}>
                      Priority
                    </th>
                    <th style={{ padding: "12px 16px", fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-muted)", textTransform: "uppercase" }}>
                      Status
                    </th>
                    <th style={{ padding: "12px 16px", fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-muted)", textTransform: "uppercase" }}>
                      Submitted
                    </th>
                    <th style={{ padding: "12px 16px", fontSize: "var(--text-xs)", fontWeight: "bold", color: "var(--color-text-muted)", textTransform: "uppercase", textAlign: "right" }}>
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {complaints.map((c) => (
                    <tr
                      key={c.id}
                      style={{ borderBottom: "1px solid var(--color-border)", transition: "background-color 0.15s" }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--color-bg-subtle)")}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                    >
                      <td style={{ padding: "14px 16px", whiteSpace: "nowrap" }}>
                        <Link
                          to={`/citizen/complaints/${c.id}`}
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: "var(--text-xs)",
                            fontWeight: "bold",
                            color: "var(--color-primary)",
                            backgroundColor: "var(--color-bg-active-nav)",
                            padding: "3px 8px",
                            borderRadius: "var(--radius-sm)",
                          }}
                        >
                          {c.complaint_number}
                        </Link>
                      </td>
                      <td style={{ padding: "14px 16px", maxWidth: "280px" }}>
                        <Link
                          to={`/citizen/complaints/${c.id}`}
                          style={{ fontWeight: "600", color: "var(--color-text-main)", fontSize: "var(--text-sm)" }}
                        >
                          {c.title}
                        </Link>
                      </td>
                      <td style={{ padding: "14px 16px", fontSize: "var(--text-sm)", color: "var(--color-text-body)", whiteSpace: "nowrap" }}>
                        {c.category_name || `Category #${c.category_id}`}
                      </td>
                      <td style={{ padding: "14px 16px", whiteSpace: "nowrap" }}>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: "bold",
                            padding: "2px 8px",
                            borderRadius: "var(--radius-sm)",
                            textTransform: "uppercase",
                            backgroundColor:
                              c.priority === "CRITICAL"
                                ? "#FEE2E2"
                                : c.priority === "HIGH"
                                ? "#FFEDD5"
                                : c.priority === "MEDIUM"
                                ? "#FEF3C7"
                                : "#F1F5F9",
                            color:
                              c.priority === "CRITICAL"
                                ? "#991B1B"
                                : c.priority === "HIGH"
                                ? "#9A3412"
                                : c.priority === "MEDIUM"
                                ? "#92400E"
                                : "#475569",
                          }}
                        >
                          {c.priority}
                        </span>
                      </td>
                      <td style={{ padding: "14px 16px", whiteSpace: "nowrap" }}>
                        <StatusBadge status={c.status} />
                      </td>
                      <td style={{ padding: "14px 16px", fontSize: "var(--text-xs)", color: "var(--color-text-muted)", whiteSpace: "nowrap" }}>
                        {formatDate(c.created_at)}
                      </td>
                      <td style={{ padding: "14px 16px", textAlign: "right", whiteSpace: "nowrap" }}>
                        <Link to={`/citizen/complaints/${c.id}`}>
                          <Button size="sm" variant={c.status === "RESOLVED_AWAITING_VERIFICATION" ? "primary" : "outline"}>
                            {c.status === "RESOLVED_AWAITING_VERIFICATION" ? "Verify Now" : "Details"}
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div style={{ marginTop: "var(--space-6)" }}>
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                onPageChange={(newPage) => setPage(newPage)}
              />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
