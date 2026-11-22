import React, { useEffect, useState, useMemo, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { adminService } from "../services/adminService";
import { categoryService } from "../services/categoryService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { StatusBadge } from "../components/StatusBadge";
import { PriorityBadge } from "../components/PriorityBadge";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { ComplaintMap } from "../components/maps/ComplaintMap";
import { isValidCoordinate } from "../components/maps/ComplaintMapMarker";

const STATUS_OPTIONS = [
  { label: "All Statuses", value: "" },
  { label: "Submitted", value: "SUBMITTED" },
  { label: "Under Review", value: "UNDER_REVIEW" },
  { label: "Assigned", value: "ASSIGNED" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Awaiting Verification", value: "RESOLVED_AWAITING_VERIFICATION" },
  { label: "Closed", value: "CLOSED" },
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

export const AdminComplaintMapPage = () => {
  const navigate = useNavigate();

  // Data states
  const [complaints, setComplaints] = useState([]);
  const [totalPlatformItems, setTotalPlatformItems] = useState(0);
  const [categories, setCategories] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter states
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [categoryIdFilter, setCategoryIdFilter] = useState("");
  const [selectedWard, setSelectedWard] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  // Map selection state
  const [selectedComplaintId, setSelectedComplaintId] = useState(null);

  // Load Categories on mount
  useEffect(() => {
    const fetchCats = async () => {
      try {
        const catList = await categoryService.getActiveCategories();
        setCategories(catList || []);
      } catch {
        // Fallback gracefully
      }
    };
    fetchCats();
  }, []);

  // Fetch Complaints across Platform
  const loadComplaints = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await adminService.listComplaints({
        page: 1,
        page_size: 100,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        category_id: categoryIdFilter ? parseInt(categoryIdFilter, 10) : undefined,
      });
      const items = Array.isArray(res.data) ? res.data : (res.data?.items || res.items || []);
      setComplaints(items);
      setTotalPlatformItems(typeof res.total_items === "number" ? res.total_items : items.length);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load platform complaints for geospatial mapping.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, priorityFilter, categoryIdFilter]);

  useEffect(() => {
    loadComplaints();
  }, [loadComplaints]);

  // Filter complaints in-memory by ward and search query
  const filteredComplaints = useMemo(() => {
    return complaints.filter((c) => {
      // Ward filter
      if (selectedWard) {
        const cWard = c.location?.area_name || c.location?.city || "";
        if (cWard.toLowerCase() !== selectedWard.toLowerCase()) {
          return false;
        }
      }

      // Search query
      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase();
        const matchNum = c.complaint_number?.toLowerCase().includes(q);
        const matchTitle = c.title?.toLowerCase().includes(q);
        const matchArea = c.location?.area_name?.toLowerCase().includes(q);
        const matchCity = c.location?.city?.toLowerCase().includes(q);
        const matchCat = c.category_name?.toLowerCase().includes(q);
        return matchNum || matchTitle || matchArea || matchCity || matchCat;
      }

      return true;
    });
  }, [complaints, selectedWard, searchTerm]);

  // Valid mapped complaints
  const mappedComplaints = useMemo(() => {
    return filteredComplaints.filter((c) => {
      return c.location && isValidCoordinate(c.location.latitude, c.location.longitude);
    });
  }, [filteredComplaints]);

  // Ward & Area aggregation breakdown (Geographic hotspots)
  const wardBreakdown = useMemo(() => {
    const counts = {};
    complaints.forEach((c) => {
      const ward = c.location?.area_name || c.location?.city || "Unspecified Area";
      counts[ward] = (counts[ward] || 0) + 1;
    });

    return Object.entries(counts)
      .map(([ward, count]) => ({ ward, count }))
      .sort((a, b) => b.count - a.count);
  }, [complaints]);

  // Selected complaint details
  const activeComplaint = useMemo(() => {
    if (!selectedComplaintId) return null;
    return complaints.find((c) => c.id === selectedComplaintId) || null;
  }, [complaints, selectedComplaintId]);

  // Key geospatial metrics
  const criticalCount = useMemo(() => {
    return mappedComplaints.filter(
      (c) => c.priority === "CRITICAL" || c.priority === "HIGH"
    ).length;
  }, [mappedComplaints]);

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <h1 className="portal-header-title">Geographic Complaint Intelligence</h1>
          <p className="portal-header-subtitle">
            Municipal geospatial distribution, ward clustering, and real-time field incident hotspots
          </p>
        </div>
        <div className="portal-header-actions">
          <Button variant="outline" size="sm" onClick={loadComplaints} disabled={isLoading}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
              <path d="M23 4v6h-6" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            Refresh Coordinates
          </Button>
          <Link to="/admin/complaints">
            <Button variant="primary" size="sm">
              Complaint Triage Queue
            </Button>
          </Link>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Geospatial Telemetry Error">
          {error}
        </Alert>
      )}

      {/* KPI Stat Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "var(--space-4)",
          marginBottom: "var(--space-4)",
        }}
      >
        <Card>
          <CardContent style={{ padding: "var(--space-4)" }}>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", fontWeight: "bold" }}>
              Total Complaints
            </div>
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)", marginTop: "var(--space-1)" }}>
              {totalPlatformItems}
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "4px" }}>
              {totalPlatformItems > complaints.length
                ? `Showing ${complaints.length} on current map`
                : "Matching filter query"}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "var(--space-4)" }}>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", fontWeight: "bold" }}>
              Mapped GPS Pins
            </div>
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-bold)", color: "var(--color-primary)", marginTop: "var(--space-1)" }}>
              {mappedComplaints.length}
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "4px" }}>
              Active on city map
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "var(--space-4)" }}>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", fontWeight: "bold" }}>
              Critical / High Severity
            </div>
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-bold)", color: criticalCount > 0 ? "var(--color-danger)" : "var(--color-success)", marginTop: "var(--space-1)" }}>
              {criticalCount}
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "4px" }}>
              Requiring rapid dispatch
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "var(--space-4)" }}>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", fontWeight: "bold" }}>
              Primary Hotspot Ward
            </div>
            <div style={{ fontSize: "var(--text-lg)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)", marginTop: "var(--space-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {wardBreakdown[0]?.ward || "No areas"}
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "4px" }}>
              {wardBreakdown[0] ? `${wardBreakdown[0].count} incidents logged` : "No activity"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Toolbar */}
      <Card style={{ marginBottom: "var(--space-4)" }}>
        <CardContent style={{ padding: "var(--space-3) var(--space-4)" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              flexWrap: "wrap",
            }}
          >
            {/* Status */}
            <div style={{ minWidth: "160px" }}>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-bg-card)",
                  fontSize: "var(--text-sm)",
                  color: "var(--color-text-main)",
                  outline: "none",
                }}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Priority */}
            <div style={{ minWidth: "150px" }}>
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-bg-card)",
                  fontSize: "var(--text-sm)",
                  color: "var(--color-text-main)",
                  outline: "none",
                }}
              >
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Category */}
            <div style={{ minWidth: "180px" }}>
              <select
                value={categoryIdFilter}
                onChange={(e) => setCategoryIdFilter(e.target.value)}
                style={{
                  width: "100%",
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
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Free Search */}
            <div style={{ minWidth: "220px", flex: 1 }}>
              <Input
                placeholder="Search reference #, title, or area..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                size="sm"
              />
            </div>

            {/* Reset Filters */}
            {(statusFilter || priorityFilter || categoryIdFilter || selectedWard || searchTerm) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setStatusFilter("");
                  setPriorityFilter("");
                  setCategoryIdFilter("");
                  setSelectedWard("");
                  setSearchTerm("");
                }}
              >
                Clear Filters
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Main Map + Side Hotspot / Inspection Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 360px",
          gap: "var(--space-4)",
          alignItems: "stretch",
        }}
        className="map-page-grid"
      >
        {/* Map Panel */}
        <div>
          <ComplaintMap
            complaints={mappedComplaints}
            selectedComplaintId={selectedComplaintId}
            onSelectComplaint={(c) => setSelectedComplaintId(c.id)}
            userRole="ADMINISTRATOR"
            height="620px"
            isLoading={isLoading}
            emptyMessage="No complaints with valid geographic coordinates match current filters."
          />
        </div>

        {/* Right Intelligence Column */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {/* Active Marker Detail Inspector */}
          {activeComplaint ? (
            <Card>
              <CardHeader style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--color-border-card)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <CardTitle style={{ fontSize: "var(--text-sm)" }}>Pinpoint Inspector</CardTitle>
                  <Button variant="ghost" size="sm" onClick={() => setSelectedComplaintId(null)}>
                    &times;
                  </Button>
                </div>
              </CardHeader>
              <CardContent style={{ padding: "var(--space-4)", display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--color-primary)" }}>
                    {activeComplaint.complaint_number}
                  </span>
                  <div style={{ display: "flex", gap: "var(--space-2)" }}>
                    <StatusBadge status={activeComplaint.status} size="sm" />
                    {activeComplaint.priority && <PriorityBadge priority={activeComplaint.priority} size="sm" />}
                  </div>
                </div>

                <div>
                  <h4 style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)", margin: "0 0 4px" }}>
                    {activeComplaint.title}
                  </h4>
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", margin: 0, lineHeight: 1.4, maxHeight: "60px", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {activeComplaint.description}
                  </p>
                </div>

                <div
                  style={{
                    backgroundColor: "var(--color-bg-app)",
                    border: "1px solid var(--color-border-card)",
                    borderRadius: "var(--radius-md)",
                    padding: "var(--space-3)",
                    fontSize: "var(--text-xs)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                  }}
                >
                  <div><strong>Category:</strong> {activeComplaint.category_name || "Uncategorized"}</div>
                  <div><strong>Ward/Area:</strong> {activeComplaint.location?.area_name || "Not specified"}</div>
                  <div><strong>Address:</strong> {activeComplaint.location?.address_line || "No address line"}</div>
                  <div><strong>Coordinates:</strong> {activeComplaint.location?.latitude}, {activeComplaint.location?.longitude}</div>
                </div>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => navigate(`/admin/complaints/${activeComplaint.id}`)}
                >
                  Open Operational Triage Dossier &rarr;
                </Button>
              </CardContent>
            </Card>
          ) : null}

          {/* Ward Hotspots Breakdown */}
          <Card style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <CardHeader style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--color-border-card)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <CardTitle style={{ fontSize: "var(--text-sm)" }}>
                  Ward Hotspots <span style={{ fontSize: "0.6875rem", fontWeight: "normal", color: "var(--color-text-muted)" }}>({complaints.length} sampled)</span>
                </CardTitle>
                {selectedWard && (
                  <button
                    type="button"
                    onClick={() => setSelectedWard("")}
                    style={{
                      background: "none",
                      border: "none",
                      fontSize: "var(--text-xs)",
                      color: "var(--color-primary)",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    View All Wards
                  </button>
                )}
              </div>
            </CardHeader>
            <CardContent
              style={{
                flex: 1,
                overflowY: "auto",
                maxHeight: activeComplaint ? "260px" : "480px",
                padding: "var(--space-2) var(--space-3)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
              }}
            >
              {wardBreakdown.length === 0 ? (
                <EmptyState title="No geographical data" description="No complaints with area tags found." />
              ) : (
                wardBreakdown.map(({ ward, count }) => {
                  const isSelected = selectedWard.toLowerCase() === ward.toLowerCase();
                  return (
                    <div
                      key={ward}
                      onClick={() => setSelectedWard(isSelected ? "" : ward)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "var(--space-2) var(--space-3)",
                        borderRadius: "var(--radius-md)",
                        border: `1px solid ${isSelected ? "var(--color-primary)" : "var(--color-border-card)"}`,
                        backgroundColor: isSelected ? "var(--color-bg-active-nav)" : "var(--color-bg-card)",
                        cursor: "pointer",
                        fontSize: "var(--text-xs)",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", overflow: "hidden" }}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                          <circle cx="12" cy="10" r="3" />
                        </svg>
                        <span style={{ fontWeight: 600, color: "var(--color-text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {ward}
                        </span>
                      </div>
                      <span
                        style={{
                          backgroundColor: isSelected ? "var(--color-primary)" : "var(--color-bg-app)",
                          color: isSelected ? "#ffffff" : "var(--color-text-muted)",
                          padding: "2px 8px",
                          borderRadius: "var(--radius-full)",
                          fontWeight: 700,
                          fontSize: "0.6875rem",
                        }}
                      >
                        {count}
                      </span>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default AdminComplaintMapPage;
