import React, { useState, useEffect } from "react";
import "./ConfirmationDialog.css";
import { Button } from "./Button";

const DialogModal = ({
  title,
  description,
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "primary",
  requireReason = false,
  reasonLabel = "Reason / Justification",
  reasonPlaceholder = "Please provide details...",
  isLoading = false,
  onConfirm,
  onCancel,
}) => {
  const [reason, setReason] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && !isLoading && onCancel) {
        onCancel();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isLoading, onCancel]);

  const handleConfirm = () => {
    if (requireReason && !reason.trim()) {
      setError("Please provide a reason to proceed.");
      return;
    }
    onConfirm(reason.trim());
  };

  return (
    <div className="dialog-overlay" onClick={onCancel} role="dialog" aria-modal="true">
      <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <h3 className="dialog-title">{title}</h3>
          <button
            type="button"
            className="dialog-close-btn"
            onClick={onCancel}
            disabled={isLoading}
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div className="dialog-body">
          <p className="dialog-desc">{description}</p>

          {requireReason && (
            <div className="dialog-reason-group">
              <label className="dialog-label">
                {reasonLabel} <span className="required-star">*</span>
              </label>
              <textarea
                className={`dialog-textarea ${error ? "has-error" : ""}`}
                rows={4}
                value={reason}
                placeholder={reasonPlaceholder}
                disabled={isLoading}
                onChange={(e) => {
                  setReason(e.target.value);
                  if (error) setError(null);
                }}
              />
              {error && <span className="dialog-error">{error}</span>}
            </div>
          )}
        </div>

        <div className="dialog-footer">
          <Button variant="outline" onClick={onCancel} disabled={isLoading}>
            {cancelText}
          </Button>
          <Button
            variant={variant === "danger" ? "secondary" : "primary"}
            onClick={handleConfirm}
            isLoading={isLoading}
            disabled={isLoading}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  );
};

export const ConfirmationDialog = (props) => {
  if (!props.isOpen) return null;
  return <DialogModal {...props} />;
};
