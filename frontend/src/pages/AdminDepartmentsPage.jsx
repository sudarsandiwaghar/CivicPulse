import React, { useState, useEffect, useCallback, useMemo } from "react";
import "./DashboardPages.css";
import "../components/ConfirmationDialog.css";
import { departmentService } from "../services/departmentService";
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

export const AdminDepartmentsPage = () => {
  const [departments, setDepartments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState("ALL"); // ALL | ACTIVE | INACTIVE
  const [searchQuery, setSearchQuery] = useState("");

  // Create Modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [createForm, setCreateForm] = useState({
    name: "",
    code: "",
    description: "",
    contact_email: "",
    contact_phone: "",
    is_active: true,
  });

  // Edit Modal
  const [editingDept, setEditingDept] = useState(null);
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState(null);
  const [editForm, setEditForm] = useState({
    name: "",
    code: "",
    description: "",
    contact_email: "",
    contact_phone: "",
    is_active: true,
  });

  // Deactivate Dialog
  const [deactivatingDept, setDeactivatingDept] = useState(null);
  const [deactivateLoading, setDeactivateLoading] = useState(false);

  const fetchDepartments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const activeParam =
        statusFilter === "ACTIVE" ? true : statusFilter === "INACTIVE" ? false : undefined;
      const data = await departmentService.listDepartments(activeParam);
      setDepartments(Array.isArray(data) ? data : data?.data || []);
    } catch (err) {
      setError(err.message || "Failed to load municipal departments.");
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchDepartments();
  }, [fetchDepartments]);

  // Client search filtering
  const filteredDepartments = useMemo(() => {
    if (!searchQuery.trim()) return departments;
    const q = searchQuery.toLowerCase().trim();
    return departments.filter((d) => {
      const name = (d.name || "").toLowerCase();
      const code = (d.code || "").toLowerCase();
      const desc = (d.description || "").toLowerCase();
      return name.includes(q) || code.includes(q) || desc.includes(q);
    });
  }, [departments, searchQuery]);

  // Metric stats
  const stats = useMemo(() => {
    const total = departments.length;
    const active = departments.filter((d) => d.is_active).length;
    const inactive = departments.filter((d) => !d.is_active).length;
    const totalWorkers = departments.reduce((acc, d) => acc + (d.workers_count || 0), 0);
    const totalCategories = departments.reduce((acc, d) => acc + (d.categories_count || 0), 0);
    return { total, active, inactive, totalWorkers, totalCategories };
  }, [departments]);

  // Create
  const handleOpenCreate = () => {
    setCreateForm({
      name: "",
      code: "",
      description: "",
      contact_email: "",
      contact_phone: "",
      is_active: true,
    });
    setCreateError(null);
    setIsCreateOpen(true);
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    setCreateError(null);

    const name = createForm.name.trim();
    const code = createForm.code.trim().toUpperCase();

    if (name.length < 2 || name.length > 100) {
      setCreateError("Department name must be between 2 and 100 characters.");
      return;
    }
    if (code.length < 2 || code.length > 20) {
      setCreateError("Department code must be between 2 and 20 alphanumeric characters.");
      return;
    }

    setCreateLoading(true);
    try {
      await departmentService.createDepartment({
        name,
        code,
        description: createForm.description.trim() || null,
        contact_email: createForm.contact_email.trim() || null,
        contact_phone: createForm.contact_phone.trim() || null,
        is_active: createForm.is_active,
      });

      setIsCreateOpen(false);
      setFeedback({
        type: "success",
        message: `Department "${name}" (${code}) successfully registered.`,
      });
      await fetchDepartments();
    } catch (err) {
      setCreateError(err.message || "Failed to create department.");
    } finally {
      setCreateLoading(false);
    }
  };

  // Edit
  const handleOpenEdit = (dept) => {
    setEditingDept(dept);
    setEditForm({
      name: dept.name || "",
      code: dept.code || "",
      description: dept.description || "",
      contact_email: dept.contact_email || "",
      contact_phone: dept.contact_phone || "",
      is_active: Boolean(dept.is_active),
    });
    setEditError(null);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editingDept) return;
    setEditError(null);

    const name = editForm.name.trim();
    const code = editForm.code.trim().toUpperCase();

    if (name.length < 2 || name.length > 100) {
      setEditError("Department name must be between 2 and 100 characters.");
      return;
    }
    if (code.length < 2 || code.length > 20) {
      setEditError("Department code must be between 2 and 20 alphanumeric characters.");
      return;
    }

    setEditLoading(true);
    try {
      await departmentService.updateDepartment(editingDept.id, {
        name,
        code,
        description: editForm.description.trim() || null,
        contact_email: editForm.contact_email.trim() || null,
        contact_phone: editForm.contact_phone.trim() || null,
        is_active: editForm.is_active,
      });

      setEditingDept(null);
      setFeedback({
        type: "success",
        message: `Department "${name}" successfully updated.`,
      });
      await fetchDepartments();
    } catch (err) {
      setEditError(err.message || "Failed to update department.");
    } finally {
      setEditLoading(false);
    }
  };

  // Deactivate
  const handleDeactivateConfirm = async () => {
    if (!deactivatingDept) return;
    setDeactivateLoading(true);
    try {
      await departmentService.deactivateDepartment(deactivatingDept.id);
      setDeactivatingDept(null);
      setFeedback({
        type: "success",
        message: `Department "${deactivatingDept.name}" deactivated.`,
      });
      await fetchDepartments();
    } catch (err) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to deactivate department.",
      });
    } finally {
      setDeactivateLoading(false);
    }
  };

  return (
    <div className="portal-page">
      {/* Page Header */}
      <div className="portal-header">
        <div>
          <h1 className="portal-header-title">Municipal Departments</h1>
          <p className="portal-header-subtitle">
            Configure municipal service departments, workforce allocation, and jurisdictional issue categories.
          </p>
        </div>
        <div className="portal-header-actions">
          <Button variant="primary" onClick={handleOpenCreate}>
            + Create Department
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

      {/* Metrics Row */}
      <div className="portal-stats-grid">
        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Total Departments
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "var(--color-text-main)" }}>
              {stats.total}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Registered divisions</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Active Departments
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "#15803d" }}>
              {stats.active}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Operational & accepting dispatches</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Linked Personnel
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "var(--color-primary)" }}>
              {stats.totalWorkers}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Allocated field workers</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Linked Categories
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "#6366f1" }}>
              {stats.totalCategories}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Covered issue domains</span>
          </CardContent>
        </Card>
      </div>

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
                placeholder="Search departments by name, code..."
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
                <option value="ALL">All Departments</option>
                <option value="ACTIVE">Active Only</option>
                <option value="INACTIVE">Inactive Only</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Department Cards Grid or Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            Department Directory ({filteredDepartments.length} {filteredDepartments.length === 1 ? "department" : "departments"})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div style={{ padding: "3rem 0", textAlign: "center" }}>
              <Spinner size="md" message="Loading municipal departments..." />
            </div>
          ) : error ? (
            <Alert variant="error">{error}</Alert>
          ) : filteredDepartments.length === 0 ? (
            <div style={{ padding: "3rem 0", textAlign: "center", color: "var(--color-text-muted)" }}>
              No departments found matching the filter criteria.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--color-border-card)", textAlign: "left", color: "var(--color-text-muted)" }}>
                    <th style={{ padding: "0.75rem" }}>Department Name</th>
                    <th style={{ padding: "0.75rem" }}>Code</th>
                    <th style={{ padding: "0.75rem" }}>Assigned Categories</th>
                    <th style={{ padding: "0.75rem" }}>Field Workforce</th>
                    <th style={{ padding: "0.75rem" }}>Contact</th>
                    <th style={{ padding: "0.75rem" }}>Status</th>
                    <th style={{ padding: "0.75rem" }}>Registered</th>
                    <th style={{ padding: "0.75rem", textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDepartments.map((d) => (
                    <tr key={d.id} style={{ borderBottom: "1px solid var(--color-border-card)" }}>
                      <td style={{ padding: "0.75rem" }}>
                        <div style={{ fontWeight: "600", color: "var(--color-text-main)" }}>{d.name}</div>
                        {d.description && (
                          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", maxWidth: "260px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {d.description}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "0.75rem" }}>
                        <code style={{ fontSize: "0.8125rem", padding: "2px 6px", backgroundColor: "var(--color-bg-app)", borderRadius: "var(--radius-sm)" }}>
                          {d.code}
                        </code>
                      </td>
                      <td style={{ padding: "0.75rem" }}>
                        <span style={{ fontWeight: "600" }}>{d.categories_count ?? "—"}</span>
                        <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}> categories</span>
                      </td>
                      <td style={{ padding: "0.75rem" }}>
                        <span style={{ fontWeight: "600" }}>{d.workers_count ?? "—"}</span>
                        <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}> technicians</span>
                      </td>
                      <td style={{ padding: "0.75rem", fontSize: "0.8125rem", color: "var(--color-text-muted)" }}>
                        {d.contact_email && <div>{d.contact_email}</div>}
                        {d.contact_phone && <div>{d.contact_phone}</div>}
                        {!d.contact_email && !d.contact_phone && <div>—</div>}
                      </td>
                      <td style={{ padding: "0.75rem" }}>
                        <span
                          style={{
                            fontSize: "0.75rem",
                            fontWeight: "600",
                            padding: "2px 8px",
                            borderRadius: "var(--radius-sm)",
                            backgroundColor: d.is_active ? "#dcfce7" : "#f1f5f9",
                            color: d.is_active ? "#15803d" : "#475569",
                          }}
                        >
                          {d.is_active ? "ACTIVE" : "INACTIVE"}
                        </span>
                      </td>
                      <td style={{ padding: "0.75rem", whiteSpace: "nowrap", color: "var(--color-text-muted)" }}>
                        {formatDate(d.created_at)}
                      </td>
                      <td style={{ padding: "0.75rem", textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: "0.5rem" }}>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleOpenEdit(d)}
                          >
                            Edit
                          </Button>
                          {d.is_active && (
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => setDeactivatingDept(d)}
                            >
                              Deactivate
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Department Modal */}
      {isCreateOpen && (
        <div className="dialog-overlay" role="dialog" aria-modal="true">
          <div className="dialog-backdrop" onClick={() => !createLoading && setIsCreateOpen(false)} />
          <div className="dialog-card" style={{ maxWidth: "520px" }}>
            <h2 className="dialog-title">Create Municipal Department</h2>
            <p className="dialog-description">
              Establish a new administrative department responsible for handling categorized civic issues.
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
                    Department Name <span style={{ color: "#e11d48" }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={createForm.name}
                    onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                    placeholder="e.g., Public Works Department"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                    Department Code <span style={{ color: "#e11d48" }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={createForm.code}
                    onChange={(e) => setCreateForm({ ...createForm, code: e.target.value.toUpperCase() })}
                    placeholder="e.g., PWD"
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
                    placeholder="Overview of jurisdiction and civic functions..."
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)", fontFamily: "inherit" }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Contact Email
                    </label>
                    <input
                      type="email"
                      value={createForm.contact_email}
                      onChange={(e) => setCreateForm({ ...createForm, contact_email: e.target.value })}
                      placeholder="pwd@city.gov"
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Contact Phone
                    </label>
                    <input
                      type="tel"
                      value={createForm.contact_phone}
                      onChange={(e) => setCreateForm({ ...createForm, contact_phone: e.target.value })}
                      placeholder="+91 80 2222 1111"
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
                    <span>Active and accepting new complaint allocations</span>
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
                  {createLoading ? "Creating..." : "Create Department"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Department Modal */}
      {editingDept && (
        <div className="dialog-overlay" role="dialog" aria-modal="true">
          <div className="dialog-backdrop" onClick={() => !editLoading && setEditingDept(null)} />
          <div className="dialog-card" style={{ maxWidth: "520px" }}>
            <h2 className="dialog-title">Edit Department: {editingDept.name}</h2>
            <p className="dialog-description">
              Modify contact information, descriptive details, or operational status.
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
                    Department Name <span style={{ color: "#e11d48" }}>*</span>
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
                    Department Code <span style={{ color: "#e11d48" }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={editForm.code}
                    onChange={(e) => setEditForm({ ...editForm, code: e.target.value.toUpperCase() })}
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
                      Contact Email
                    </label>
                    <input
                      type="email"
                      value={editForm.contact_email}
                      onChange={(e) => setEditForm({ ...editForm, contact_email: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Contact Phone
                    </label>
                    <input
                      type="tel"
                      value={editForm.contact_phone}
                      onChange={(e) => setEditForm({ ...editForm, contact_phone: e.target.value })}
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
                    <span>Active and accepting new complaint allocations</span>
                  </label>
                </div>
              </div>

              <div className="dialog-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={editLoading}
                  onClick={() => setEditingDept(null)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={editLoading}
                >
                  {editLoading ? "Saving..." : "Save Changes"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Deactivate Confirmation Dialog */}
      {deactivatingDept && (
        <div className="dialog-overlay" role="dialog" aria-modal="true">
          <div className="dialog-backdrop" onClick={() => !deactivateLoading && setDeactivatingDept(null)} />
          <div className="dialog-card">
            <h2 className="dialog-title" style={{ color: "#e11d48" }}>Deactivate Department</h2>
            <p className="dialog-description">
              Are you sure you want to deactivate <strong>{deactivatingDept.name} ({deactivatingDept.code})</strong>?
              Deactivated departments cannot receive new complaint allocations. All existing complaints and worker histories remain fully preserved.
            </p>

            <div className="dialog-actions">
              <Button
                variant="secondary"
                disabled={deactivateLoading}
                onClick={() => setDeactivatingDept(null)}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                disabled={deactivateLoading}
                onClick={handleDeactivateConfirm}
              >
                {deactivateLoading ? "Deactivating..." : "Confirm Deactivation"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDepartmentsPage;
