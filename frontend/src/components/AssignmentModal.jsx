import React, { useState, useEffect } from "react";
import "./ConfirmationDialog.css";
import { Button } from "./Button";
import { Spinner } from "./Spinner";
import { Alert } from "./Alert";
import { adminService } from "../services/adminService";

export const AssignmentModal = ({
  isOpen,
  mode = "assign", // "assign" | "reassign"
  complaint,
  currentWorkerId = null,
  isLoading = false,
  onConfirm,
  onCancel,
}) => {
  const [workers, setWorkers] = useState([]);
  const [selectedWorkerId, setSelectedWorkerId] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [workersLoading, setWorkersLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !complaint) return;

    setSelectedWorkerId("");
    setReason("");
    setNotes("");
    setError(null);

    const loadEligibleWorkers = async () => {
      setWorkersLoading(true);
      try {
        // Query active and available workers
        const res = await adminService.listWorkers({
          is_available: true,
          employment_status: "ACTIVE",
          page: 1,
          page_size: 100,
        });
        const items = res.data || [];

        // If complaint has a category with a known department, filter or sort by department
        setWorkers(items);
      } catch {
        setError("Failed to load available field workers.");
      } finally {
        setWorkersLoading(false);
      }
    };

    loadEligibleWorkers();
  }, [isOpen, complaint]);

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

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!selectedWorkerId) {
      setError("Please select a designated field worker.");
      return;
    }

    if (mode === "reassign" && selectedWorkerId === currentWorkerId) {
      setError("Replacement worker cannot be identical to the currently assigned worker.");
      return;
    }

    if (mode === "reassign" && (!reason.trim() || reason.trim().length < 5)) {
      setError("Reassignment justification must contain at least 5 characters.");
      return;
    }

    onConfirm({
      workerId: selectedWorkerId,
      reason: reason.trim(),
      notes: notes.trim() || undefined,
    });
  };

  return (
    <div className="dialog-overlay" onClick={onCancel} role="dialog" aria-modal="true">
      <div className="dialog-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 540 }}>
        <div className="dialog-header">
          <h3 className="dialog-title">
            {mode === "reassign" ? "Reassign Field Technician" : "Assign Complaint to Technician"}
          </h3>
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
              {mode === "reassign"
                ? `Reassigning will supersede the active assignment on complaint ${complaint?.complaint_number || ""} and transition the work order to the designated replacement technician.`
                : `Designate an active, eligible field technician to investigate and remediate complaint ${complaint?.complaint_number || ""}.`}
            </p>

            {error && (
              <div style={{ marginBottom: "var(--space-3)" }}>
                <Alert variant="error" title="Assignment Error">
                  {error}
                </Alert>
              </div>
            )}

            {/* Worker Selection Dropdown */}
            <div className="dialog-reason-group">
              <label className="dialog-label">
                Select Field Technician <span className="required-star">*</span>
              </label>

              {workersLoading ? (
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 8 }}>
                  <Spinner size="sm" />
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                    Loading available workers...
                  </span>
                </div>
              ) : (
                <select
                  value={selectedWorkerId}
                  onChange={(e) => {
                    setSelectedWorkerId(e.target.value);
                    setError(null);
                  }}
                  disabled={isLoading}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--color-border)",
                    fontSize: "var(--text-sm)",
                    backgroundColor: "#fff",
                    color: "var(--color-text-main)",
                  }}
                >
                  <option value="">-- Choose Eligible Technician --</option>
                  {workers
                    .filter((w) => mode !== "reassign" || w.id !== currentWorkerId)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.full_name || "Technician"} ({w.employee_id}) — {w.department_name || "Department"} {w.designation ? `• ${w.designation}` : ""}
                      </option>
                    ))}
                </select>
              )}
            </div>

            {/* Reassignment Reason (Mandatory for reassign) */}
            {mode === "reassign" && (
              <div className="dialog-reason-group" style={{ marginTop: "var(--space-3)" }}>
                <label className="dialog-label">
                  Reassignment Justification <span className="required-star">*</span>
                </label>
                <textarea
                  className="dialog-textarea"
                  rows={3}
                  value={reason}
                  placeholder="e.g. Technician unavailable; reassigning to available sector crew..."
                  disabled={isLoading}
                  onChange={(e) => {
                    setReason(e.target.value);
                    setError(null);
                  }}
                />
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4 }}>
                  Minimum 5 non-whitespace characters required for audit trail.
                </div>
              </div>
            )}

            {/* Dispatch Instructions / Notes */}
            <div className="dialog-reason-group" style={{ marginTop: "var(--space-3)" }}>
              <label className="dialog-label">
                Dispatch Instructions / Special Notes (Optional)
              </label>
              <textarea
                className="dialog-textarea"
                rows={3}
                value={notes}
                placeholder="e.g. Bring asphalt patching roller; incident located near junction..."
                disabled={isLoading}
                onChange={(e) => setNotes(e.target.value)}
              />
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
              variant="primary"
              disabled={isLoading || !selectedWorkerId || (mode === "reassign" && reason.trim().length < 5)}
            >
              {isLoading ? "Assigning..." : mode === "reassign" ? "Confirm Reassignment" : "Dispatch Work Order"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
