import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import "./DashboardPages.css";
import "../components/ConfirmationDialog.css";
import { slaService } from "../services/slaService";
import { categoryService } from "../services/categoryService";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";

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

export const AdminSLAPoliciesPage = () => {
  const [policies, setPolicies] = useState([]);
  const [categories, setCategories] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState("ALL"); // ALL | ACTIVE | INACTIVE
  const [searchQuery, setSearchQuery] = useState("");

  // Create Policy Modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [createForm, setCreateForm] = useState({
    name: "",
    description: "",
    category_id: "",
    priority: "",
    response_time_hours: 4,
    resolution_time_hours: 48,
    is_active: true,
  });

  // Edit Policy Modal
  const [editingPolicy, setEditingPolicy] = useState(null);
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState(null);
  const [editForm, setEditForm] = useState({
    name: "",
    description: "",
    response_time_hours: 4,
    resolution_time_hours: 48,
    is_active: true,
  });

  // Load categories
  useEffect(() => {
    categoryService.getCategories().then(setCategories).catch(() => {});
  }, []);

  // Fetch policies
  const fetchPolicies = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const activeParam = statusFilter === "ACTIVE" ? true : undefined;
      const data = await slaService.listPolicies(activeParam);
      setPolicies(data);
    } catch (err) {
      setError(err.message || "Failed to load SLA policies.");
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  // Client filtering
  const filteredPolicies = useMemo(() => {
    return policies.filter((p) => {
      if (statusFilter === "ACTIVE" && !p.is_active) return false;
      if (statusFilter === "INACTIVE" && p.is_active) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const name = (p.name || "").toLowerCase();
        const desc = (p.description || "").toLowerCase();
        return name.includes(q) || desc.includes(q);
      }
      return true;
    });
  }, [policies, statusFilter, searchQuery]);

  // Create submit
  const handleOpenCreate = () => {
    setCreateForm({
      name: "",
      description: "",
      category_id: "",
      priority: "",
      response_time_hours: 4,
      resolution_time_hours: 48,
      is_active: true,
    });
    setCreateError(null);
    setIsCreateOpen(true);
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    setCreateError(null);

    const name = createForm.name.trim();
    if (!name) {
      setCreateError("Policy name cannot be empty.");
      return;
    }
    if (createForm.response_time_hours <= 0) {
      setCreateError("Target response time must be greater than 0 hours.");
      return;
    }
    if (createForm.resolution_time_hours <= 0) {
      setCreateError("Target resolution time must be greater than 0 hours.");
      return;
    }

    setCreateLoading(true);
    try {
      const payload = {
        name,
        description: createForm.description.trim() || null,
        category_id: createForm.category_id ? parseInt(createForm.category_id, 10) : null,
        priority: createForm.priority || null,
        response_time_hours: parseInt(createForm.response_time_hours, 10),
        resolution_time_hours: parseInt(createForm.resolution_time_hours, 10),
        is_active: createForm.is_active,
      };

      await slaService.createPolicy(payload);
      setIsCreateOpen(false);
      setFeedback({
        type: "success",
        message: `SLA Policy "${name}" successfully defined.`,
      });
      await fetchPolicies();
    } catch (err) {
      setCreateError(err.message || "Failed to create SLA policy.");
    } finally {
      setCreateLoading(false);
    }
  };

  // Edit submit
  const handleOpenEdit = (policy) => {
    setEditingPolicy(policy);
    setEditForm({
      name: policy.name || "",
      description: policy.description || "",
      response_time_hours: policy.response_time_hours || 4,
      resolution_time_hours: policy.resolution_time_hours || 48,
      is_active: Boolean(policy.is_active),
    });
    setEditError(null);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editingPolicy) return;
    setEditError(null);

    const name = editForm.name.trim();
    if (!name) {
      setEditError("Policy name cannot be empty.");
      return;
    }
    if (editForm.response_time_hours <= 0) {
      setEditError("Target response time must be greater than 0 hours.");
      return;
    }
    if (editForm.resolution_time_hours <= 0) {
      setEditError("Target resolution time must be greater than 0 hours.");
      return;
    }

    setEditLoading(true);
    try {
      await slaService.updatePolicy(editingPolicy.id, {
        name,
        description: editForm.description.trim() || null,
        response_time_hours: parseInt(editForm.response_time_hours, 10),
        resolution_time_hours: parseInt(editForm.resolution_time_hours, 10),
        is_active: editForm.is_active,
      });

      setEditingPolicy(null);
      setFeedback({
        type: "success",
        message: `SLA Policy "${name}" updated successfully.`,
      });
      await fetchPolicies();
    } catch (err) {
      setEditError(err.message || "Failed to update SLA policy.");
    } finally {
      setEditLoading(false);
    }
  };

  // Toggle active
  const handleToggleActive = async (policy) => {
    try {
      await slaService.updatePolicy(policy.id, {
        is_active: !policy.is_active,
      });
      setFeedback({
        type: "success",
        message: `Policy "${policy.name}" ${!policy.is_active ? "activated" : "deactivated"}.`,
      });
      await fetchPolicies();
    } catch (err) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to toggle policy status.",
      });
    }
  };

  const getCategoryName = (catId) => {
    if (!catId) return null;
    const found = categories.find((c) => c.id === catId);
    return found ? found.name : `Category #${catId}`;
  };

  return (
    <div className="portal-page">
      {/* Header */}
      <div className="portal-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <h1 className="portal-header-title">SLA Policy Configuration</h1>
          </div>
          <p className="portal-header-subtitle">
            Configure response and resolution targets, priority overrides, and category escalation thresholds.
          </p>
        </div>

        <div className="portal-header-actions" style={{ flexWrap: "wrap" }}>
          <Link to="/admin/sla">
            <Button variant="outline">
              &larr; View Live SLA Dashboard
            </Button>
          </Link>
          <Button variant="primary" onClick={handleOpenCreate}>
            + Create SLA Policy
          </Button>
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

      {/* Precedence Banner */}
      <Card>
        <CardContent style={{ padding: "1.25rem" }}>
          <div style={{ fontSize: "0.875rem" }}>
            <h3 style={{ fontSize: "0.9375rem", fontWeight: "700", color: "var(--color-text-main)", marginBottom: "0.5rem" }}>
              Policy Resolution Hierarchy (Precedence Rules)
            </h3>
            <p style={{ color: "var(--color-text-muted)", margin: "0 0 0.75rem", lineHeight: 1.5 }}>
              When a complaint is filed, the engine resolves the most specific matching policy according to the following strict precedence order:
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.75rem" }}>
              <div style={{ padding: "0.75rem", backgroundColor: "#f0fdfa", borderRadius: "var(--radius-md)", border: "1px solid #99f6e4" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: "700", color: "#0f766e" }}>1. CATEGORY + PRIORITY</div>
                <div style={{ fontSize: "0.8125rem", color: "var(--color-text-main)", marginTop: "2px" }}>Most specific override (e.g. Roads + Urgent)</div>
              </div>
              <div style={{ padding: "0.75rem", backgroundColor: "#f0fdf4", borderRadius: "var(--radius-md)", border: "1px solid #99f6e4" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: "700", color: "#0f766e" }}>2. CATEGORY SPECIFIC</div>
                <div style={{ fontSize: "0.8125rem", color: "var(--color-text-main)", marginTop: "2px" }}>Applies to all priorities in category</div>
              </div>
              <div style={{ padding: "0.75rem", backgroundColor: "#f0fdf4", borderRadius: "var(--radius-md)", border: "1px solid #99f6e4" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: "700", color: "#0f766e" }}>3. PRIORITY SPECIFIC</div>
                <div style={{ fontSize: "0.8125rem", color: "var(--color-text-main)", marginTop: "2px" }}>Applies to priority across categories</div>
              </div>
              <div style={{ padding: "0.75rem", backgroundColor: "#f0fdf4", borderRadius: "var(--radius-md)", border: "1px solid #99f6e4" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: "700", color: "#0f766e" }}>4. GLOBAL DEFAULT</div>
                <div style={{ fontSize: "0.8125rem", color: "var(--color-text-main)", marginTop: "2px" }}>Baseline fallback for all complaints</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filter and Search Bar */}
      <Card>
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
                placeholder="Search policies by name, description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              />
            </div>

            <div style={{ display: "flex", gap: "0.75rem" }}>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <option value="ALL">All Policies</option>
                <option value="ACTIVE">Active Policies Only</option>
                <option value="INACTIVE">Inactive Policies Only</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Policies Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            Configured Policies ({filteredPolicies.length} policies)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div style={{ padding: "3rem 0", textAlign: "center" }}>
              <Spinner size="md" message="Loading SLA policy rules..." />
            </div>
          ) : error ? (
            <Alert variant="error">{error}</Alert>
          ) : filteredPolicies.length === 0 ? (
            <div style={{ padding: "3rem 0", textAlign: "center", color: "var(--color-text-muted)" }}>
              No SLA policies match the selected filter.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--color-border-card)", textAlign: "left", color: "var(--color-text-muted)" }}>
                    <th style={{ padding: "0.75rem" }}>Policy Name</th>
                    <th style={{ padding: "0.75rem" }}>Scope / Specificity</th>
                    <th style={{ padding: "0.75rem" }}>Response Target</th>
                    <th style={{ padding: "0.75rem" }}>Resolution Target</th>
                    <th style={{ padding: "0.75rem" }}>Status</th>
                    <th style={{ padding: "0.75rem" }}>Created</th>
                    <th style={{ padding: "0.75rem", textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPolicies.map((p) => {
                    const isGlobal = !p.category_id && !p.priority;
                    const isCategoryOnly = p.category_id && !p.priority;
                    const isPriorityOnly = !p.category_id && p.priority;
                    const isSpecific = p.category_id && p.priority;

                    return (
                      <tr key={p.id} style={{ borderBottom: "1px solid var(--color-border-card)" }}>
                        <td style={{ padding: "0.75rem" }}>
                          <div style={{ fontWeight: "700", color: "var(--color-text-main)" }}>
                            {p.name}
                          </div>
                          {p.description && (
                            <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", maxWidth: "260px" }}>
                              {p.description}
                            </div>
                          )}
                        </td>

                        <td style={{ padding: "0.75rem" }}>
                          {isGlobal && (
                            <span style={{ fontSize: "0.75rem", fontWeight: "600", padding: "2px 8px", borderRadius: "var(--radius-sm)", backgroundColor: "#f1f5f9", color: "#475569" }}>
                              Global Default
                            </span>
                          )}
                          {isCategoryOnly && (
                            <div style={{ fontSize: "0.8125rem" }}>
                              Category: <strong>{getCategoryName(p.category_id)}</strong>
                            </div>
                          )}
                          {isPriorityOnly && (
                            <div style={{ fontSize: "0.8125rem" }}>
                              Priority: <strong>{p.priority}</strong>
                            </div>
                          )}
                          {isSpecific && (
                            <div style={{ fontSize: "0.8125rem" }}>
                              <div>Category: <strong>{getCategoryName(p.category_id)}</strong></div>
                              <div>Priority: <strong>{p.priority}</strong></div>
                            </div>
                          )}
                        </td>

                        <td style={{ padding: "0.75rem" }}>
                          <span style={{ fontWeight: "700", color: "var(--color-primary)" }}>
                            {p.response_time_hours} hours
                          </span>
                          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                            Triage Target
                          </div>
                        </td>

                        <td style={{ padding: "0.75rem" }}>
                          <span style={{ fontWeight: "700", color: "#087f8c" }}>
                            {p.resolution_time_hours} hours
                          </span>
                          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                            Remediation Target
                          </div>
                        </td>

                        <td style={{ padding: "0.75rem" }}>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              fontWeight: "600",
                              padding: "2px 8px",
                              borderRadius: "var(--radius-sm)",
                              backgroundColor: p.is_active ? "#dcfce7" : "#f1f5f9",
                              color: p.is_active ? "#15803d" : "#475569",
                            }}
                          >
                            {p.is_active ? "ACTIVE" : "INACTIVE"}
                          </span>
                        </td>

                        <td style={{ padding: "0.75rem", whiteSpace: "nowrap", color: "var(--color-text-muted)" }}>
                          {formatDate(p.created_at)}
                        </td>

                        <td style={{ padding: "0.75rem", textAlign: "right" }}>
                          <div style={{ display: "inline-flex", gap: "0.5rem" }}>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenEdit(p)}
                            >
                              Edit Targets
                            </Button>
                            <Button
                              variant={p.is_active ? "secondary" : "primary"}
                              size="sm"
                              onClick={() => handleToggleActive(p)}
                            >
                              {p.is_active ? "Deactivate" : "Activate"}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Policy Modal */}
      {isCreateOpen && (
        <div className="dialog-overlay" role="dialog" aria-modal="true">
          <div className="dialog-backdrop" onClick={() => !createLoading && setIsCreateOpen(false)} />
          <div className="dialog-card" style={{ maxWidth: "540px" }}>
            <h2 className="dialog-title">Define New SLA Policy</h2>
            <p className="dialog-description">
              Establish dual response and resolution thresholds for automatic monitoring and escalation.
            </p>

            {createError && (
              <div style={{ marginBottom: "1rem" }}>
                <Alert variant="error">{createError}</Alert>
              </div>
            )}

            <form onSubmit={handleCreateSubmit}>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem", margin: "1rem 0" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                    Policy Name <span style={{ color: "#e11d48" }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={createForm.name}
                    onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                    placeholder="e.g., Critical Infrastructure Fast Track"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                    Description
                  </label>
                  <textarea
                    rows={2}
                    value={createForm.description}
                    onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                    placeholder="Scope, operational justification, or team instructions..."
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)", fontFamily: "inherit" }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Category Scope
                    </label>
                    <select
                      value={createForm.category_id}
                      onChange={(e) => setCreateForm({ ...createForm, category_id: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    >
                      <option value="">All Categories (Global / Priority)</option>
                      {categories.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Priority Scope
                    </label>
                    <select
                      value={createForm.priority}
                      onChange={(e) => setCreateForm({ ...createForm, priority: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    >
                      <option value="">All Priorities</option>
                      <option value="URGENT">Urgent</option>
                      <option value="HIGH">High</option>
                      <option value="MEDIUM">Medium</option>
                      <option value="LOW">Low</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Response Target (Hours) <span style={{ color: "#e11d48" }}>*</span>
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={8760}
                      required
                      value={createForm.response_time_hours}
                      onChange={(e) => setCreateForm({ ...createForm, response_time_hours: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Resolution Target (Hours) <span style={{ color: "#e11d48" }}>*</span>
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={8760}
                      required
                      value={createForm.resolution_time_hours}
                      onChange={(e) => setCreateForm({ ...createForm, resolution_time_hours: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.875rem", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={createForm.is_active}
                      onChange={(e) => setCreateForm({ ...createForm, is_active: e.target.checked })}
                    />
                    <span>Active for SLA resolution matching immediately</span>
                  </label>
                </div>
              </div>

              <div className="dialog-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={createLoading}
                  onClick={() => setIsCreateOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={createLoading}
                >
                  {createLoading ? "Creating..." : "Create SLA Policy"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Policy Modal */}
      {editingPolicy && (
        <div className="dialog-overlay" role="dialog" aria-modal="true">
          <div className="dialog-backdrop" onClick={() => !editLoading && setEditingPolicy(null)} />
          <div className="dialog-card" style={{ maxWidth: "520px" }}>
            <h2 className="dialog-title">Edit SLA Policy Targets</h2>
            <p className="dialog-description">
              Update name, descriptions, or duration targets for {editingPolicy.name}.
            </p>

            {editError && (
              <div style={{ marginBottom: "1rem" }}>
                <Alert variant="error">{editError}</Alert>
              </div>
            )}

            <form onSubmit={handleEditSubmit}>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem", margin: "1rem 0" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                    Policy Name <span style={{ color: "#e11d48" }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                    Description
                  </label>
                  <textarea
                    rows={2}
                    value={editForm.description}
                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)", fontFamily: "inherit" }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Response Target (Hours) <span style={{ color: "#e11d48" }}>*</span>
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={8760}
                      required
                      value={editForm.response_time_hours}
                      onChange={(e) => setEditForm({ ...editForm, response_time_hours: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Resolution Target (Hours) <span style={{ color: "#e11d48" }}>*</span>
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={8760}
                      required
                      value={editForm.resolution_time_hours}
                      onChange={(e) => setEditForm({ ...editForm, resolution_time_hours: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.875rem", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={editForm.is_active}
                      onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                    />
                    <span>Active policy</span>
                  </label>
                </div>
              </div>

              <div className="dialog-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={editLoading}
                  onClick={() => setEditingPolicy(null)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={editLoading}
                >
                  {editLoading ? "Saving..." : "Save Policy Targets"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminSLAPoliciesPage;
