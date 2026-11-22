import React, { useEffect, useState, useMemo, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { complaintService } from "../services/complaintService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { StatusBadge } from "../components/StatusBadge";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { ComplaintMap } from "../components/maps/ComplaintMap";
import { isValidCoordinate } from "../components/maps/ComplaintMapMarker";

const STATUS_FILTERS = [
  { label: "All Statuses", value: "" },
  { label: "Submitted", value: "SUBMITTED" },
  { label: "Under Review", value: "UNDER_REVIEW" },
  { label: "Assigned", value: "ASSIGNED" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Awaiting Verification", value: "RESOLVED_AWAITING_VERIFICATION" },
  { label: "Closed & Verified", value: "CLOSED" },
  { label: "Rejected", value: "REJECTED" },
  { label: "On Hold", value: "ON_HOLD" },
];

export const CitizenComplaintMapPage = () => {
  const navigate = useNavigate();

  const [complaints, setComplaints] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [statusFilter, setStatusFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedComplaintId, setSelectedComplaintId] = useState(null);

  // Fetch all complaints for current citizen
  const loadComplaints = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await complaintService.listComplaints({
        page: 1,
        page_size: 100,
        status: statusFilter || undefined,
      });
      const items = Array.isArray(res.data) ? res.data : (res.data?.items || res.items || []);
      setComplaints(items);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load your complaints for map visualization.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadComplaints();
  }, [loadComplaints]);

  // Filter complaints by search term
  const filteredComplaints = useMemo(() => {
    if (!searchTerm.trim()) return complaints;
    const q = searchTerm.toLowerCase();
    return complaints.filter((c) => {
      const matchNum = c.complaint_number?.toLowerCase().includes(q);
      const matchTitle = c.title?.toLowerCase().includes(q);
      const matchArea = c.location?.area_name?.toLowerCase().includes(q);
      const matchCity = c.location?.city?.toLowerCase().includes(q);
      return matchNum || matchTitle || matchArea || matchCity;
    });
  }, [complaints, searchTerm]);

  // Split mapped vs unmapped complaints
  const { mappedComplaints, unmappedCount } = useMemo(() => {
    const mapped = [];
    let unmapped = 0;
    filteredComplaints.forEach((c) => {
      if (c.location && isValidCoordinate(c.location.latitude, c.location.longitude)) {
        mapped.push(c);
      } else {
        unmapped++;
      }
    });
    return { mappedComplaints: mapped, unmappedCount: unmapped };
  }, [filteredComplaints]);

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <h1 className="portal-header-title">My Complaints Map</h1>
          <p className="portal-header-subtitle">
            Geographic view of your submitted civic complaints with real-time status markers
          </p>
        </div>
        <div className="portal-header-actions">
          <Link to="/citizen/complaints">
            <Button variant="outline" size="sm">
              List View
            </Button>
          </Link>
          <Link to="/citizen/report">
            <Button variant="primary" size="sm">
              Report Civic Issue
            </Button>
          </Link>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Geographic Data Error">
          {error}
        </Alert>
      )}

      {/* Filter and Overview Controls */}
      <Card style={{ marginBottom: "var(--space-4)" }}>
        <CardContent style={{ padding: "var(--space-3) var(--space-4)" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "var(--space-3)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap", flex: 1 }}>
              <div style={{ minWidth: "180px" }}>
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
                  {STATUS_FILTERS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ minWidth: "220px", flex: 1, maxWidth: "360px" }}>
                <Input
                  placeholder="Search by ID, title, or area..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  size="sm"
                />
              </div>
            </div>

            {/* Metric pill counter */}
            <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
              <span
                style={{
                  padding: "4px 8px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: "var(--color-bg-active-nav)",
                  color: "var(--color-primary)",
                  fontWeight: 600,
                }}
              >
                {mappedComplaints.length} Mapped Pins
              </span>
              {unmappedCount > 0 && (
                <span
                  style={{
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    backgroundColor: "rgba(107, 114, 128, 0.1)",
                    color: "var(--color-text-muted)",
                  }}
                >
                  {unmappedCount} Missing Coords
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Map + Sidebar Layout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 340px",
          gap: "var(--space-4)",
          alignItems: "stretch",
        }}
        className="map-page-grid"
      >
        {/* Map Column */}
        <div>
          <ComplaintMap
            complaints={mappedComplaints}
            selectedComplaintId={selectedComplaintId}
            onSelectComplaint={(c) => setSelectedComplaintId(c.id)}
            userRole="CITIZEN"
            height="580px"
            isLoading={isLoading}
            emptyMessage="No complaints with geographic coordinates found."
          />
        </div>

        {/* Complaints Side List */}
        <div>
          <Card style={{ height: "100%", display: "flex", flexDirection: "column" }}>
            <CardHeader style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--color-border-card)" }}>
              <CardTitle style={{ fontSize: "var(--text-sm)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Incident Feed</span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: "normal" }}>
                  {filteredComplaints.length} total
                </span>
              </CardTitle>
            </CardHeader>

            <CardContent
              style={{
                flex: 1,
                overflowY: "auto",
                maxHeight: "520px",
                padding: "var(--space-2) var(--space-3)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
              }}
            >
              {isLoading ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "var(--space-8)" }}>
                  <Spinner size="md" />
                  <span style={{ marginTop: "var(--space-2)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                    Loading complaints...
                  </span>
                </div>
              ) : filteredComplaints.length === 0 ? (
                <EmptyState
                  title="No complaints found"
                  description="Try adjusting your status or search filters."
                />
              ) : (
                filteredComplaints.map((c) => {
                  const isSelected = selectedComplaintId === c.id;
                  const hasCoords = c.location && isValidCoordinate(c.location.latitude, c.location.longitude);

                  return (
                    <div
                      key={c.id}
                      onClick={() => {
                        if (hasCoords) {
                          setSelectedComplaintId(c.id);
                        }
                      }}
                      style={{
                        padding: "var(--space-3)",
                        borderRadius: "var(--radius-md)",
                        border: `1px solid ${isSelected ? "var(--color-primary)" : "var(--color-border-card)"}`,
                        backgroundColor: isSelected ? "var(--color-bg-active-nav)" : "var(--color-bg-card)",
                        cursor: hasCoords ? "pointer" : "default",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-2)", marginBottom: "4px" }}>
                        <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--color-primary)" }}>
                          {c.complaint_number}
                        </span>
                        <StatusBadge status={c.status} size="sm" />
                      </div>

                      <div style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)", color: "var(--color-text-main)", marginBottom: "4px", lineHeight: 1.3 }}>
                        {c.title}
                      </div>

                      <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "flex", alignItems: "center", gap: "4px" }}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                          <circle cx="12" cy="10" r="3" />
                        </svg>
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {c.location?.area_name ? `${c.location.area_name}, ${c.location.city}` : c.location?.city || "No area recorded"}
                        </span>
                      </div>

                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "var(--space-2)", paddingTop: "var(--space-2)", borderTop: "1px dashed var(--color-border)" }}>
                        <span style={{ fontSize: "0.6875rem", color: hasCoords ? "var(--color-primary)" : "var(--color-text-muted)" }}>
                          {hasCoords ? `Lat: ${Number(c.location.latitude).toFixed(3)}, Lng: ${Number(c.location.longitude).toFixed(3)}` : "No GPS coords"}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/citizen/complaints/${c.id}`);
                          }}
                          style={{
                            background: "none",
                            border: "none",
                            padding: 0,
                            color: "var(--color-primary)",
                            fontSize: "var(--text-xs)",
                            fontWeight: "var(--weight-bold)",
                            cursor: "pointer",
                          }}
                        >
                          View Details &rarr;
                        </button>
                      </div>
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

export default CitizenComplaintMapPage;
