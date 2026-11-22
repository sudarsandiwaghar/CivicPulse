import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { categoryService } from "../services/categoryService";
import { complaintService } from "../services/complaintService";
import { ApiError } from "../types/api";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Alert } from "../components/Alert";
import { Spinner } from "../components/Spinner";
import { LocationPicker } from "../components/maps/LocationPicker";
import { DEFAULT_MUNICIPAL_CITY } from "../components/maps/mapConstants";

export const CitizenReportPage = () => {
  const navigate = useNavigate();

  // Categories
  const [categories, setCategories] = useState([]);
  const [isCategoriesLoading, setIsCategoriesLoading] = useState(true);

  // Form Fields
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");

  // Location Fields (unpinned by default until citizen selects on map or GPS)
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [areaName, setAreaName] = useState("");
  const [city, setCity] = useState(DEFAULT_MUNICIPAL_CITY);
  const [pincode, setPincode] = useState("");
  const [landmark, setLandmark] = useState("");

  // Form Validation & Submission State
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState(null);
  const [createdComplaint, setCreatedComplaint] = useState(null);

  useEffect(() => {
    const loadCategories = async () => {
      try {
        const catList = await categoryService.getActiveCategories();
        setCategories(catList);
        if (catList.length > 0) {
          setCategoryId(catList[0].id.toString());
        }
      } catch {
        setSubmissionError("Failed to load civic categories. Please check your network connection.");
      } finally {
        setIsCategoriesLoading(false);
      }
    };
    loadCategories();
  }, []);

  const validate = () => {
    const errs = {};

    if (!title.trim()) {
      errs.title = "Issue title is required";
    } else if (title.trim().length < 5) {
      errs.title = "Title must be at least 5 characters";
    } else if (title.trim().length > 200) {
      errs.title = "Title cannot exceed 200 characters";
    }

    if (!description.trim()) {
      errs.description = "Description is required";
    } else if (description.trim().length < 10) {
      errs.description = "Description must be at least 10 characters";
    } else if (description.trim().length > 2000) {
      errs.description = "Description cannot exceed 2000 characters";
    }

    if (!categoryId) {
      errs.categoryId = "Please select a category";
    }

    if (!latitude || !longitude) {
      errs.latitude = "Please select the incident location on the map or use GPS";
    } else {
      const lat = parseFloat(latitude);
      if (isNaN(lat) || lat < -90.0 || lat > 90.0) {
        errs.latitude = "Latitude must be a valid number between -90 and 90";
      }

      const lng = parseFloat(longitude);
      if (isNaN(lng) || lng < -180.0 || lng > 180.0) {
        errs.longitude = "Longitude must be a valid number between -180 and 180";
      }
    }

    if (!city.trim()) {
      errs.city = "City name is required";
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmissionError(null);

    if (!validate()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await complaintService.createComplaint({
        title: title.trim(),
        description: description.trim(),
        category_id: parseInt(categoryId, 10),
        location: {
          latitude: parseFloat(latitude),
          longitude: parseFloat(longitude),
          address_line: addressLine.trim() || undefined,
          area_name: areaName.trim() || undefined,
          city: city.trim(),
          pincode: pincode.trim() || undefined,
          landmark: landmark.trim() || undefined,
        },
      });

      setCreatedComplaint(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmissionError(err.message);
      } else {
        setSubmissionError("An unexpected error occurred while filing the complaint. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (createdComplaint) {
    return (
      <div className="portal-page" style={{ maxWidth: "680px", margin: "var(--space-8) auto" }}>
        <Card>
          <CardContent>
            <div style={{ textAlign: "center", padding: "var(--space-8) var(--space-4)" }}>
              <div
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "var(--color-bg-active-nav)",
                  color: "var(--color-primary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto var(--space-4)",
                }}
              >
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>

              <h2 style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)", marginBottom: "var(--space-2)" }}>
                Complaint Successfully Registered
              </h2>
              <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-6)" }}>
                Your issue has been logged into the municipal queue. The system has initiated the response SLA clock.
              </p>

              <div
                style={{
                  backgroundColor: "var(--color-bg-app)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-md)",
                  padding: "var(--space-4)",
                  marginBottom: "var(--space-6)",
                  display: "inline-block",
                  minWidth: "260px",
                }}
              >
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", fontWeight: "bold" }}>
                  Tracking Reference Code
                </div>
                <div
                  style={{
                    fontSize: "var(--text-2xl)",
                    fontFamily: "var(--font-mono)",
                    fontWeight: "var(--weight-bold)",
                    color: "var(--color-primary)",
                    marginTop: "var(--space-1)",
                  }}
                >
                  {createdComplaint.complaint_number}
                </div>
              </div>

              <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "center", flexWrap: "wrap" }}>
                <Button variant="primary" onClick={() => navigate(`/citizen/complaints/${createdComplaint.id}`)}>
                  View Complaint Details & Timeline
                </Button>
                <Button variant="outline" onClick={() => navigate("/citizen")}>
                  Return to Dashboard
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setCreatedComplaint(null);
                    setTitle("");
                    setDescription("");
                    setLatitude("");
                    setLongitude("");
                    setAddressLine("");
                    setAreaName("");
                    setCity(DEFAULT_MUNICIPAL_CITY);
                    setPincode("");
                    setLandmark("");
                  }}
                >
                  Report Another Issue
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="portal-page" style={{ maxWidth: "800px", margin: "0 auto" }}>
      {/* Header */}
      <div className="portal-header">
        <div>
          <h1 className="portal-header-title">Report a Civic Problem</h1>
          <p className="portal-header-subtitle">
            Provide issue information and location to dispatch municipal resolution teams
          </p>
        </div>
        <div className="portal-header-actions">
          <Link to="/citizen/complaints">
            <Button variant="outline" size="sm">
              View My Existing Reports
            </Button>
          </Link>
        </div>
      </div>

      {submissionError && (
        <Alert variant="error" title="Submission Failed">
          {submissionError}
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Issue Information</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} noValidate style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
            {/* Category Select */}
            <div>
              <label style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)", color: "var(--color-text-main)", marginBottom: "var(--space-1)" }}>
                Civic Category <span style={{ color: "var(--color-danger)" }}>*</span>
              </label>
              {isCategoriesLoading ? (
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", padding: "var(--space-2)" }}>
                  <Spinner size="sm" />
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>Loading active categories...</span>
                </div>
              ) : (
                <select
                  value={categoryId}
                  onChange={(e) => {
                    setCategoryId(e.target.value);
                    if (errors.categoryId) setErrors((prev) => ({ ...prev, categoryId: "" }));
                  }}
                  disabled={isSubmitting}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: "var(--radius-md)",
                    border: `1px solid ${errors.categoryId ? "var(--color-danger)" : "var(--color-border)"}`,
                    backgroundColor: "var(--color-bg-card)",
                    fontSize: "var(--text-sm)",
                    color: "var(--color-text-main)",
                    outline: "none",
                  }}
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.department_name ? `(${c.department_name})` : ""}
                    </option>
                  ))}
                </select>
              )}
              {errors.categoryId && (
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-danger)", marginTop: "4px", display: "block" }}>
                  {errors.categoryId}
                </span>
              )}
            </div>

            {/* Title */}
            <Input
              label="Headline / Title"
              required
              placeholder="e.g. Broken streetlight on 4th Main Road"
              helperText="Minimum 5 characters. Keep it clear and concise."
              value={title}
              error={errors.title}
              disabled={isSubmitting}
              onChange={(e) => {
                setTitle(e.target.value);
                if (errors.title) setErrors((prev) => ({ ...prev, title: "" }));
              }}
            />

            {/* Description */}
            <div>
              <label style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)", color: "var(--color-text-main)", marginBottom: "var(--space-1)" }}>
                Detailed Problem Description <span style={{ color: "var(--color-danger)" }}>*</span>
              </label>
              <textarea
                rows={5}
                placeholder="Explain the specific issue, extent of damage, safety hazards, or surrounding conditions..."
                value={description}
                disabled={isSubmitting}
                onChange={(e) => {
                  setDescription(e.target.value);
                  if (errors.description) setErrors((prev) => ({ ...prev, description: "" }));
                }}
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: "var(--radius-md)",
                  border: `1px solid ${errors.description ? "var(--color-danger)" : "var(--color-border)"}`,
                  backgroundColor: "var(--color-bg-card)",
                  fontSize: "var(--text-sm)",
                  fontFamily: "inherit",
                  resize: "vertical",
                  color: "var(--color-text-main)",
                  outline: "none",
                }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px" }}>
                <span style={{ fontSize: "var(--text-xs)", color: errors.description ? "var(--color-danger)" : "var(--color-text-muted)" }}>
                  {errors.description || "Minimum 10 characters"}
                </span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {description.length} / 2000
                </span>
              </div>
            </div>

            {/* Location Section */}
            <div style={{ paddingTop: "var(--space-4)", borderTop: "1px solid var(--color-border)" }}>
              <div style={{ marginBottom: "var(--space-3)" }}>
                <h3 style={{ fontSize: "var(--text-base)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)", margin: 0 }}>
                  Incident Location & Map Pinpoint
                </h3>
                <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "4px" }}>
                  Use the map or GPS detection below to locate the issue, or enter coordinates and address details.
                </p>
              </div>

              {/* Interactive Map Picker */}
              <LocationPicker
                latitude={latitude}
                longitude={longitude}
                disabled={isSubmitting}
                onLocationChange={({ latitude: newLat, longitude: newLng }) => {
                  setLatitude(newLat);
                  setLongitude(newLng);
                  if (errors.latitude) setErrors((prev) => ({ ...prev, latitude: "" }));
                  if (errors.longitude) setErrors((prev) => ({ ...prev, longitude: "" }));
                }}
              />

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
                <Input
                  label="Latitude"
                  type="text"
                  required
                  placeholder="e.g. 12.9716"
                  value={latitude}
                  error={errors.latitude}
                  disabled={isSubmitting}
                  onChange={(e) => {
                    setLatitude(e.target.value);
                    if (errors.latitude) setErrors((prev) => ({ ...prev, latitude: "" }));
                  }}
                />
                <Input
                  label="Longitude"
                  type="text"
                  required
                  placeholder="e.g. 77.5946"
                  value={longitude}
                  error={errors.longitude}
                  disabled={isSubmitting}
                  onChange={(e) => {
                    setLongitude(e.target.value);
                    if (errors.longitude) setErrors((prev) => ({ ...prev, longitude: "" }));
                  }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
                <Input
                  label="Street Address / Road Segment"
                  placeholder="e.g. 100 Feet Road, Near Metro Pillar 45"
                  value={addressLine}
                  disabled={isSubmitting}
                  onChange={(e) => setAddressLine(e.target.value)}
                />
                <Input
                  label="Area / Ward"
                  placeholder="e.g. Indiranagar"
                  value={areaName}
                  disabled={isSubmitting}
                  onChange={(e) => setAreaName(e.target.value)}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-3)" }}>
                <Input
                  label="City"
                  required
                  placeholder="e.g. Bengaluru"
                  value={city}
                  error={errors.city}
                  disabled={isSubmitting}
                  onChange={(e) => {
                    setCity(e.target.value);
                    if (errors.city) setErrors((prev) => ({ ...prev, city: "" }));
                  }}
                />
                <Input
                  label="Postal Code (Pincode)"
                  placeholder="e.g. 560038"
                  value={pincode}
                  disabled={isSubmitting}
                  onChange={(e) => setPincode(e.target.value)}
                />
                <Input
                  label="Prominent Landmark"
                  placeholder="e.g. Opp. BDA Complex"
                  value={landmark}
                  disabled={isSubmitting}
                  onChange={(e) => setLandmark(e.target.value)}
                />
              </div>
            </div>

            {/* Attachment note */}
            <div
              style={{
                backgroundColor: "var(--color-bg-app)",
                border: "1px dashed var(--color-border)",
                borderRadius: "var(--radius-md)",
                padding: "var(--space-4)",
                display: "flex",
                alignItems: "flex-start",
                gap: "var(--space-3)",
              }}
            >
              <div style={{ color: "var(--color-primary)", marginTop: 2 }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                </svg>
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", lineHeight: "var(--leading-relaxed)" }}>
                <strong style={{ color: "var(--color-text-main)" }}>Attachment Evidence Notice:</strong>
                <br />
                Direct photographic evidence uploading is being integrated in a future release. Your submitted text details and coordinates will be logged directly into the municipal dispatch system.
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-3)", marginTop: "var(--space-4)" }}>
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate("/citizen")}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                isLoading={isSubmitting}
                disabled={isSubmitting || isCategoriesLoading}
              >
                Submit Civic Complaint
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};
