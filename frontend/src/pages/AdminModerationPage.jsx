import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import "./DashboardPages.css";
import { adminService } from "../services/adminService";
import { categoryService } from "../services/categoryService";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { Pagination } from "../components/Pagination";
import { StatusBadge } from "../components/StatusBadge";
import { PublicModerationModal } from "../components/PublicModerationModal";

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

export const AdminModerationPage = () => {
  const [complaints, setComplaints] = useState([]);
  const [categories, setCategories] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);

  // Filters
  const [activeTab, setActiveTab] = useState("ALL"); // ALL | PUBLISHED | UNLISTED
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 12;

  // Moderation Modal
  const [selectedComplaint, setSelectedComplaint] = useState(null);
  const [moderationMode, setModerationMode] = useState("PUBLISH"); // PUBLISH | UPDATE | REVOKE
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Load categories
  useEffect(() => {
    categoryService.getCategories().then(setCategories).catch(() => {});
  }, []);

  // Fetch complaints
  const fetchComplaints = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Fetch complaints with a large batch to filter moderation status on client side
      const filters = {
        page: 1,
        page_size: 100,
        sort_by: "created_at",
        sort_order: "desc",
      };
      if (selectedCategoryId) {
        filters.category_id = selectedCategoryId;
      }

      const res = await adminService.listComplaints(filters);
      setComplaints(res.data || []);
    } catch (err) {
      setError(err.message || "Failed to load complaints for moderation.");
    } finally {
      setIsLoading(false);
    }
  }, [selectedCategoryId]);

  useEffect(() => {
    fetchComplaints();
  }, [fetchComplaints]);

  // Client filtering for publication status and search
  const filteredComplaints = useMemo(() => {
    return complaints.filter((c) => {
      // Filter by tab
      if (activeTab === "PUBLISHED" && !c.is_public) return false;
      if (activeTab === "UNLISTED" && c.is_public) return false;

      // Filter by search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const num = (c.complaint_number || "").toLowerCase();
        const title = (c.title || "").toLowerCase();
        const pTitle = (c.public_title || "").toLowerCase();
        const citizen = (c.citizen_name || "").toLowerCase();
        if (!num.includes(q) && !title.includes(q) && !pTitle.includes(q) && !citizen.includes(q)) {
          return false;
        }
      }

      return true;
    });
  }, [complaints, activeTab, searchQuery]);

  // Client pagination
  const totalItems = filteredComplaints.length;
  const totalPages = Math.ceil(totalItems / pageSize) || 1;
  const displayedComplaints = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredComplaints.slice(start, start + pageSize);
  }, [filteredComplaints, page, pageSize]);

  // Stats
  const stats = useMemo(() => {
    const total = complaints.length;
    const published = complaints.filter((c) => c.is_public).length;
    const unlisted = total - published;
    return { total, published, unlisted };
  }, [complaints]);

  // Modal handlers
  const handleOpenModeration = (complaint, mode) => {
    setSelectedComplaint(complaint);
    setModerationMode(mode);
    setIsModalOpen(true);
  };

  const handleModerationConfirm = async (payload) => {
    if (!selectedComplaint) return;
    setActionLoading(true);
    try {
      await adminService.moderatePublic(selectedComplaint.id, payload);
      setIsModalOpen(false);
      setFeedback({
        type: "success",
        message: `Successfully executed ${payload.action} for complaint ${selectedComplaint.complaint_number}.`,
      });
      await fetchComplaints();
    } catch (err) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to update public content moderation.",
      });
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="portal-page">
      {/* Page Header */}
      <div className="portal-header">
        <div>
          <h1 className="portal-header-title">Public Feed Moderation</h1>
          <p className="portal-header-subtitle">
            Curate, sanitize, approve, or revoke civic complaints published to the civic community public feed.
          </p>
        </div>
      </div>

      {feedback && (
        <Alert
          variant={feedback.type}
          dismissible
          onDismiss={() => setFeedback(null)}
        >
          {feedback.message}
        </Alert>
      )}

      {/* Summary Cards */}
      <div className="portal-stats-grid">
        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Total Audited Complaints
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "var(--color-text-main)" }}>
              {stats.total}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Registered in system</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Published to Public Feed
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "#15803d" }}>
              {stats.published}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Visible to civic community</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Internal / Unlisted
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "#64748b" }}>
              {stats.unlisted}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Restricted to reporting citizen & staff</span>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Tab Bar */}
      <Card>
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid var(--color-border-card)",
            padding: "0 1.25rem",
            gap: "1.5rem",
          }}
        >
          <button
            onClick={() => { setActiveTab("ALL"); setPage(1); }}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "ALL" ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: activeTab === "ALL" ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: activeTab === "ALL" ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
            }}
          >
            All Complaints ({stats.total})
          </button>

          <button
            onClick={() => { setActiveTab("PUBLISHED"); setPage(1); }}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "PUBLISHED" ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: activeTab === "PUBLISHED" ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: activeTab === "PUBLISHED" ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
            }}
          >
            Published ({stats.published})
          </button>

          <button
            onClick={() => { setActiveTab("UNLISTED"); setPage(1); }}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: activeTab === "UNLISTED" ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: activeTab === "UNLISTED" ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: activeTab === "UNLISTED" ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
            }}
          >
            Unlisted ({stats.unlisted})
          </button>
        </div>

        <CardContent style={{ padding: "1rem 1.25rem" }}>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "1rem",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ flex: "1 1 240px", maxWidth: "340px" }}>
              <input
                type="text"
                placeholder="Search by ID, title, citizen name..."
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
                style={{
                  width: "100%",
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              />
            </div>

            <div>
              <select
                value={selectedCategoryId}
                onChange={(e) => { setSelectedCategoryId(e.target.value); setPage(1); }}
                style={{
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <option value="">All Categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Moderation Complaints Grid/Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            Moderation Directory ({filteredComplaints.length} {filteredComplaints.length === 1 ? "complaint" : "complaints"})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div style={{ padding: "3rem 0", textAlign: "center" }}>
              <Spinner size="md" message="Loading moderation records..." />
            </div>
          ) : error ? (
            <Alert variant="error">{error}</Alert>
          ) : displayedComplaints.length === 0 ? (
            <div style={{ padding: "3rem 0", textAlign: "center", color: "var(--color-text-muted)" }}>
              No complaints found matching the selected moderation filters.
            </div>
          ) : (
            <>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {displayedComplaints.map((c) => (
                  <div
                    key={c.id}
                    style={{
                      padding: "1.25rem",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--color-border-card)",
                      backgroundColor: c.is_public ? "#f0fdf4" : "var(--color-bg-card)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.75rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.25rem" }}>
                          <Link
                            to={`/admin/complaints/${c.id}`}
                            style={{ fontWeight: "700", color: "var(--color-primary)", textDecoration: "none" }}
                          >
                            {c.complaint_number}
                          </Link>
                          <StatusBadge status={c.status} size="sm" />
                          <span
                            style={{
                              fontSize: "0.75rem",
                              fontWeight: "600",
                              padding: "2px 8px",
                              borderRadius: "var(--radius-sm)",
                              backgroundColor: c.is_public ? "#dcfce7" : "#f1f5f9",
                              color: c.is_public ? "#15803d" : "#475569",
                            }}
                          >
                            {c.is_public ? "PUBLIC (PUBLISHED)" : "UNLISTED"}
                          </span>
                        </div>
                        <h3 style={{ fontSize: "1rem", fontWeight: "600", margin: "0.25rem 0", color: "var(--color-text-main)" }}>
                          {c.title}
                        </h3>
                        <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                          Filed by: <strong>{c.citizen_name || "Citizen"}</strong> &bull; Category: {c.category_name} &bull; Date: {formatDate(c.created_at)}
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                        {!c.is_public ? (
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleOpenModeration(c, "PUBLISH")}
                          >
                            Publish to Feed
                          </Button>
                        ) : (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenModeration(c, "UPDATE")}
                            >
                              Edit Public Copy
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => handleOpenModeration(c, "REVOKE")}
                            >
                              Revoke
                            </Button>
                          </>
                        )}
                        <Link to={`/admin/complaints/${c.id}`}>
                          <Button variant="secondary" size="sm">
                            View Dossier
                          </Button>
                        </Link>
                      </div>
                    </div>

                    {/* Approved Public Copy Section if published */}
                    {c.is_public && (
                      <div
                        style={{
                          padding: "0.75rem 1rem",
                          borderRadius: "var(--radius-sm)",
                          backgroundColor: "#ffffff",
                          border: "1px solid #bbf7d0",
                          fontSize: "0.875rem",
                        }}
                      >
                        <div style={{ fontSize: "0.75rem", fontWeight: "700", textTransform: "uppercase", color: "#15803d", marginBottom: "0.25rem" }}>
                          Approved Public Feed Headline & Narrative:
                        </div>
                        <div style={{ fontWeight: "600", color: "var(--color-text-main)" }}>
                          {c.public_title || c.title}
                        </div>
                        <div style={{ fontSize: "0.8125rem", color: "var(--color-text-muted)", marginTop: "0.25rem" }}>
                          {c.public_description || c.description}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {totalPages > 1 && (
                <div style={{ marginTop: "1.5rem" }}>
                  <Pagination
                    currentPage={page}
                    totalPages={totalPages}
                    onPageChange={setPage}
                  />
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Public Moderation Modal */}
      {selectedComplaint && (
        <PublicModerationModal
          isOpen={isModalOpen}
          mode={moderationMode}
          complaint={selectedComplaint}
          isLoading={actionLoading}
          onConfirm={handleModerationConfirm}
          onCancel={() => setIsModalOpen(false)}
        />
      )}
    </div>
  );
};

export default AdminModerationPage;
