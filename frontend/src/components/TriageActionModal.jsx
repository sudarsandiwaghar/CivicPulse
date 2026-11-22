import React, { useState, useEffect } from "react";
import "./ConfirmationDialog.css";
import { Button } from "./Button";
import { Alert } from "./Alert";
import { categoryService } from "../services/categoryService";

const PRIORITY_CHOICES = [
  { label: "Low", value: "LOW" },
  { label: "Medium", value: "MEDIUM" },
  { label: "High", value: "HIGH" },
  { label: "Urgent", value: "URGENT" },
];

export const TriageActionModal = ({
  isOpen,
  actionType, // 'UNDER_REVIEW' | 'REJECTED' | 'DUPLICATE' | 'ON_HOLD' | 'ADJUST_PRIORITY' | 'RECLASSIFY_CATEGORY'
  complaint,
  isLoading = false,
  onConfirm,
  onCancel,
}) => {
  const [categories, setCategories] = useState([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedPriority, setSelectedPriority] = useState("");
  const [originalComplaintId, setOriginalComplaintId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !complaint) return;

    setSelectedCategoryId(complaint.category_id || "");
    setSelectedPriority(complaint.priority || "MEDIUM");
    setOriginalComplaintId("");
    setReason("");
    setError(null);

    if (actionType === "RECLASSIFY_CATEGORY") {
      categoryService.getCategories().then(setCategories).catch(() => {});
    }
  }, [isOpen, actionType, complaint]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && !isLoading && onCancel) {
        onCancel();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isLoading, onCancel]);

  if (!isOpen || !complaint) return null;

  let modalTitle = "Administrative Triage Action";
  let confirmBtnText = "Confirm Action";
  let isReasonMandatory = true;

  switch (actionType) {
    case "UNDER_REVIEW":
      modalTitle = "Accept Complaint for Administrative Review";
      confirmBtnText = "Begin Review";
      isReasonMandatory = false;
      break;
    case "REJECTED":
      modalTitle = "Reject Civic Complaint";
      confirmBtnText = "Reject Complaint";
      isReasonMandatory = true;
      break;
    case "DUPLICATE":
      modalTitle = "Mark Complaint as Duplicate";
      confirmBtnText = "Mark as Duplicate";
      isReasonMandatory = true;
      break;
    case "ON_HOLD":
      modalTitle = "Place Complaint on Operational Hold";
      confirmBtnText = "Place on Hold";
      isReasonMandatory = true;
      break;
    case "ADJUST_PRIORITY":
      modalTitle = "Adjust Operational Priority";
      confirmBtnText = "Update Priority";
      isReasonMandatory = true;
      break;
    case "RECLASSIFY_CATEGORY":
      modalTitle = "Reclassify Complaint Category";
      confirmBtnText = "Update Category";
      isReasonMandatory = false;
      break;
    default:
      break;
  }

  const handleSubmit = (e) => {
    e.preventDefault();
    setError(null);

    if (isReasonMandatory && (!reason.trim() || reason.trim().length < 5)) {
      setError("Please provide a justification reason containing at least 5 characters.");
      return;
    }

    if (actionType === "DUPLICATE" && !originalComplaintId.trim()) {
      setError("Please provide the original complaint UUID to merge duplicates.");
      return;
    }

    if (actionType === "RECLASSIFY_CATEGORY" && (!selectedCategoryId || Number(selectedCategoryId) === complaint.category_id)) {
      setError("Please select a different category to reclassify.");
      return;
    }

    onConfirm({
      actionType,
      reason: reason.trim(),
      priority: actionType === "ADJUST_PRIORITY" ? selectedPriority : undefined,
      categoryId: actionType === "RECLASSIFY_CATEGORY" ? Number(selectedCategoryId) : undefined,
      originalComplaintId: actionType === "DUPLICATE" ? originalComplaintId.trim() : undefined,
    });
  };

  return (
    <div className="dialog-overlay" onClick={onCancel} role="dialog" aria-modal="true">
      <div className="dialog-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
        <div className="dialog-header">
          <h3 className="dialog-title">{modalTitle}</h3>
          <button
            type="button"
            className="dialog-close-btn"
            onClick={onCancel}
            disabled={isLoading}
            aria-label="Close dialog"
          >
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="dialog-body">
            <p className="dialog-desc">
              Complaint Reference: <strong>{complaint.complaint_number}</strong>
            </p>

            {error && (
              <div style={{ marginBottom: "var(--space-3)" }}>
                <Alert variant="error" title="Triage Validation">
                  {error}
                </Alert>
              </div>
            )}

            {/* Category selector if reclassifying */}
            {actionType === "RECLASSIFY_CATEGORY" && (
              <div className="dialog-reason-group">
                <label className="dialog-label">
                  New Category <span className="required-star">*</span>
                </label>
                <select
                  value={selectedCategoryId}
                  onChange={(e) => setSelectedCategoryId(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--color-border)",
                    fontSize: "var(--text-sm)",
                    backgroundColor: "#fff",
                  }}
                >
                  <option value="">-- Select Category --</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.department_name || "Department"})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Priority selector if adjusting priority */}
            {actionType === "ADJUST_PRIORITY" && (
              <div className="dialog-reason-group">
                <label className="dialog-label">
                  Adjust Operational Priority <span className="required-star">*</span>
                </label>
                <select
                  value={selectedPriority}
                  onChange={(e) => setSelectedPriority(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--color-border)",
                    fontSize: "var(--text-sm)",
                    backgroundColor: "#fff",
                  }}
                >
                  {PRIORITY_CHOICES.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Original Complaint UUID if duplicate */}
            {actionType === "DUPLICATE" && (
              <div className="dialog-reason-group">
                <label className="dialog-label">
                  Original Complaint UUID <span className="required-star">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
                  value={originalComplaintId}
                  onChange={(e) => setOriginalComplaintId(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--color-border)",
                    fontSize: "var(--text-sm)",
                  }}
                />
              </div>
            )}

            {/* Recorded Justification / Reason */}
            <div className="dialog-reason-group" style={{ marginTop: "var(--space-3)" }}>
              <label className="dialog-label">
                Operational Justification / Audit Remarks {isReasonMandatory && <span className="required-star">*</span>}
              </label>
              <textarea
                className="dialog-textarea"
                rows={3}
                value={reason}
                placeholder={
                  actionType === "REJECTED"
                    ? "Explain why this complaint is out of municipal scope or invalid..."
                    : actionType === "ON_HOLD"
                    ? "Detail required materials, pending approvals, or external dependencies..."
                    : "Enter administrative triage notes..."
                }
                disabled={isLoading}
                onChange={(e) => setReason(e.target.value)}
              />
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4 }}>
                {isReasonMandatory ? "Minimum 5 characters required for administrative audit log." : "Optional administrative note recorded in status history."}
              </div>
            </div>
          </div>

          <div className="dialog-footer">
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant={actionType === "REJECTED" ? "danger" : "primary"}
              disabled={isLoading || (isReasonMandatory && reason.trim().length < 5)}
            >
              {isLoading ? "Processing..." : confirmBtnText}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
