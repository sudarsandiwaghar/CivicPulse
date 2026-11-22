import React, { useState, useEffect } from "react";
import "./ConfirmationDialog.css";
import { Button } from "./Button";
import { Alert } from "./Alert";

export const PublicModerationModal = ({
  isOpen,
  mode = "PUBLISH", // "PUBLISH" | "UPDATE" | "REVOKE"
  complaint,
  isLoading = false,
  onConfirm,
  onCancel,
}) => {
  const [publicTitle, setPublicTitle] = useState("");
  const [publicDescription, setPublicDescription] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !complaint) return;

    setError(null);
    if (mode === "REVOKE") {
      setPublicTitle("");
      setPublicDescription("");
    } else {
      // Pre-fill with sanitized defaults from complaint
      setPublicTitle(complaint.public_title || complaint.title || "");
      setPublicDescription(complaint.public_description || complaint.description || "");
    }
  }, [isOpen, mode, complaint]);

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

  const handleSubmit = (e) => {
    e.preventDefault();
    setError(null);

    if (mode === "REVOKE") {
      onConfirm({ action: "REVOKE" });
      return;
    }

    const trimmedTitle = publicTitle.trim();
    const trimmedDesc = publicDescription.trim();

    if (trimmedTitle.length < 5 || trimmedTitle.length > 200) {
      setError("Sanitized public headline must be between 5 and 200 characters.");
      return;
    }

    if (trimmedDesc.length < 10 || trimmedDesc.length > 2000) {
      setError("Sanitized public description must be between 10 and 2000 characters.");
      return;
    }

    onConfirm({
      action: mode,
      public_title: trimmedTitle,
      public_description: trimmedDesc,
    });
  };

  return (
    <div className="dialog-overlay" onClick={onCancel} role="dialog" aria-modal="true">
      <div className="dialog-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 540 }}>
        <div className="dialog-header">
          <h3 className="dialog-title">
            {mode === "REVOKE"
              ? "Revoke Public Publication"
              : mode === "UPDATE"
              ? "Update Approved Public Content"
              : "Publish Complaint to Community Feed"}
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
            {mode === "REVOKE" ? (
              <p className="dialog-desc">
                Revoking publication will immediately remove complaint <strong>{complaint.complaint_number}</strong> from the public feed and community follower feeds. It remains visible in administrative and citizen personal records.
              </p>
            ) : (
              <p className="dialog-desc">
                Publishing surfaces this civic issue on the verified public community bulletin. Review the sanitized title and description below to ensure no citizen PII, street addresses, or private phone numbers are exposed.
              </p>
            )}

            {error && (
              <div style={{ marginBottom: "var(--space-3)" }}>
                <Alert variant="error" title="Moderation Error">
                  {error}
                </Alert>
              </div>
            )}

            {mode !== "REVOKE" && (
              <>
                <div className="dialog-reason-group">
                  <label className="dialog-label">
                    Approved Public Headline <span className="required-star">*</span>
                  </label>
                  <input
                    type="text"
                    value={publicTitle}
                    placeholder="e.g. Water main repair at Sector 4..."
                    disabled={isLoading}
                    onChange={(e) => setPublicTitle(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--color-border)",
                      fontSize: "var(--text-sm)",
                    }}
                  />
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4 }}>
                    <span>5 to 200 characters</span>
                    <span>{publicTitle.length}/200</span>
                  </div>
                </div>

                <div className="dialog-reason-group" style={{ marginTop: "var(--space-3)" }}>
                  <label className="dialog-label">
                    Approved Public Description <span className="required-star">*</span>
                  </label>
                  <textarea
                    className="dialog-textarea"
                    rows={4}
                    value={publicDescription}
                    placeholder="e.g. Municipal PWD crew dispatched to investigate pipeline pressure drop near Central Market..."
                    disabled={isLoading}
                    onChange={(e) => setPublicDescription(e.target.value)}
                  />
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4 }}>
                    <span>10 to 2000 characters</span>
                    <span>{publicDescription.length}/2000</span>
                  </div>
                </div>
              </>
            )}
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
              variant={mode === "REVOKE" ? "danger" : "primary"}
              disabled={isLoading}
            >
              {isLoading
                ? "Processing..."
                : mode === "REVOKE"
                ? "Confirm Revocation"
                : mode === "UPDATE"
                ? "Save Approved Content"
                : "Approve & Publish"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
