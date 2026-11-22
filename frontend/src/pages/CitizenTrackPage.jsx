import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { complaintService } from "../services/complaintService";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Alert } from "../components/Alert";
import { Spinner } from "../components/Spinner";
import { ComplaintCard } from "../components/ComplaintCard";

export const CitizenTrackPage = () => {
  const navigate = useNavigate();

  const [trackingCode, setTrackingCode] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState(null);
  const [searchResults, setSearchResults] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    const query = trackingCode.trim();
    if (!query) {
      setError("Please enter a tracking reference number or keyword.");
      return;
    }

    setIsSearching(true);
    setError(null);
    setHasSearched(true);

    try {
      // First try exact complaint number match, fallback to general search
      const res = await complaintService.listComplaints({
        search: query,
        page: 1,
        page_size: 10,
      });

      setSearchResults(res.data);
      if (res.data.length === 1 && res.data[0].complaint_number.toLowerCase() === query.toLowerCase()) {
        navigate(`/citizen/complaints/${res.data[0].id}`);
      }
    } catch {
      setError("Unable to search complaints. Please check your network connection.");
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="portal-page" style={{ maxWidth: "780px", margin: "0 auto" }}>
      {/* Header */}
      <div className="portal-header">
        <div>
          <h1 className="portal-header-title">Track Civic Complaint</h1>
          <p className="portal-header-subtitle">
            Enter your tracking reference number to inspect real-time progress and SLA milestones
          </p>
        </div>
      </div>

      <Card>
        <CardContent>
          <form onSubmit={handleSearch} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 320px" }}>
                <Input
                  placeholder="e.g. CP-2026-10001 or keyword"
                  value={trackingCode}
                  onChange={(e) => {
                    setTrackingCode(e.target.value);
                    if (error) setError(null);
                  }}
                  disabled={isSearching}
                />
              </div>
              <Button type="submit" variant="primary" isLoading={isSearching} disabled={isSearching}>
                Lookup Status
              </Button>
            </div>

            {error && <Alert variant="error">{error}</Alert>}

            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              Tip: You can find your reference code in your submission receipt or in your <a href="/citizen/complaints">complaint history</a>.
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Results */}
      {isSearching ? (
        <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-8) 0" }}>
          <Spinner size="md" />
          <span style={{ marginLeft: "var(--space-2)", color: "var(--color-text-muted)" }}>Searching municipal records...</span>
        </div>
      ) : hasSearched ? (
        <Card>
          <CardHeader>
            <CardTitle>Matching Records ({searchResults.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {searchResults.length === 0 ? (
              <div style={{ textAlign: "center", padding: "var(--space-6) 0", color: "var(--color-text-muted)" }}>
                <p>No complaints found matching "{trackingCode}".</p>
                <p style={{ fontSize: "var(--text-xs)", marginTop: "var(--space-2)" }}>
                  Please check the reference number and verify that you authored the complaint.
                </p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {searchResults.map((c) => (
                  <ComplaintCard
                    key={c.id}
                    id={c.id}
                    complaintNumber={c.complaint_number}
                    title={c.title}
                    categoryName={c.category_name || `Category #${c.category_id}`}
                    status={c.status}
                    priority={c.priority}
                    createdAt={c.created_at}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
};
