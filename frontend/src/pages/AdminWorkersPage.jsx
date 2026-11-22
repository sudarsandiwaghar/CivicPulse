import React, { useState, useEffect, useCallback, useMemo } from "react";
import "./DashboardPages.css";
import "../components/ConfirmationDialog.css";
import { adminService } from "../services/adminService";
import { departmentService } from "../services/departmentService";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { Pagination } from "../components/Pagination";

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

export const AdminWorkersPage = () => {
  const [workers, setWorkers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);

  // Filters
  const [selectedDeptId, setSelectedDeptId] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("ALL"); // ALL | ACTIVE | ON_LEAVE | INACTIVE
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 15;

  // Modals state
  const [isProvisionOpen, setIsProvisionOpen] = useState(false);
  const [provisionLoading, setProvisionLoading] = useState(false);
  const [provisionError, setProvisionError] = useState(null);
  const [provisionForm, setProvisionForm] = useState({
    full_name: "",
    email: "",
    password: "",
    employee_id: "",
    department_id: "",
    designation: "",
    phone_number: "",
  });

  const [editingWorker, setEditingWorker] = useState(null);
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState(null);
  const [editForm, setEditForm] = useState({
    full_name: "",
    department_id: "",
    designation: "",
    phone_number: "",
    employment_status: "ACTIVE",
    is_available: true,
  });

  const [deactivatingWorker, setDeactivatingWorker] = useState(null);
  const [deactivateLoading, setDeactivateLoading] = useState(false);

  // Load departments list for dropdowns
  useEffect(() => {
    departmentService.listDepartments()
      .then((data) => {
        setDepartments(Array.isArray(data) ? data : data?.data || []);
      })
      .catch(() => {});
  }, []);

  // Fetch workers
  const fetchWorkers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = {
        page: 1,
        page_size: 100, // Fetch up to 100 for comprehensive admin view & client search
      };
      if (selectedDeptId) {
        params.department_id = parseInt(selectedDeptId, 10);
      }
      if (selectedStatus !== "ALL") {
        params.employment_status = selectedStatus;
      }

      const res = await adminService.listWorkers(params);
      setWorkers(res.data || []);
    } catch (err) {
      setError(err.message || "Failed to load field workers list.");
    } finally {
      setIsLoading(false);
    }
  }, [selectedDeptId, selectedStatus]);

  useEffect(() => {
    fetchWorkers();
  }, [fetchWorkers]);

  // Client search filtering
  const filteredWorkers = useMemo(() => {
    if (!searchQuery.trim()) return workers;
    const query = searchQuery.toLowerCase().trim();
    return workers.filter((w) => {
      const name = (w.full_name || "").toLowerCase();
      const email = (w.email || "").toLowerCase();
      const empId = (w.employee_id || "").toLowerCase();
      const dept = (w.department_name || "").toLowerCase();
      return name.includes(query) || email.includes(query) || empId.includes(query) || dept.includes(query);
    });
  }, [workers, searchQuery]);

  // Client pagination
  const totalItems = filteredWorkers.length;
  const totalPages = Math.ceil(totalItems / pageSize) || 1;
  const displayedWorkers = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredWorkers.slice(start, start + pageSize);
  }, [filteredWorkers, page, pageSize]);

  // Aggregate summary counts
  const stats = useMemo(() => {
    const total = workers.length;
    const active = workers.filter((w) => w.employment_status === "ACTIVE").length;
    const available = workers.filter((w) => w.is_available && w.employment_status === "ACTIVE").length;
    const onLeave = workers.filter((w) => w.employment_status === "ON_LEAVE").length;
    const inactive = workers.filter((w) => w.employment_status === "INACTIVE").length;
    return { total, active, available, onLeave, inactive };
  }, [workers]);

  // Provisioning
  const handleOpenProvision = () => {
    setProvisionForm({
      full_name: "",
      email: "",
      password: "",
      employee_id: "",
      department_id: departments[0]?.id ? String(departments[0].id) : "",
      designation: "",
      phone_number: "",
    });
    setProvisionError(null);
    setIsProvisionOpen(true);
  };

  const handleProvisionSubmit = async (e) => {
    e.preventDefault();
    setProvisionError(null);

    if (!provisionForm.full_name.trim() || provisionForm.full_name.length < 2) {
      setProvisionError("Full name must be at least 2 characters.");
      return;
    }
    if (!provisionForm.email.includes("@")) {
      setProvisionError("A valid email address is required.");
      return;
    }
    if (provisionForm.password.length < 8) {
      setProvisionError("Temporary password must be at least 8 characters.");
      return;
    }
    if (!provisionForm.employee_id.trim() || provisionForm.employee_id.length < 2) {
      setProvisionError("Employee badge ID must be at least 2 characters.");
      return;
    }
    if (!provisionForm.department_id) {
      setProvisionError("Please assign the field worker to a municipal department.");
      return;
    }

    setProvisionLoading(true);
    try {
      await adminService.createWorker({
        full_name: provisionForm.full_name.trim(),
        email: provisionForm.email.trim(),
        password: provisionForm.password,
        employee_id: provisionForm.employee_id.trim().toUpperCase(),
        department_id: parseInt(provisionForm.department_id, 10),
        designation: provisionForm.designation.trim() || null,
        phone_number: provisionForm.phone_number.trim() || null,
      });

      setIsProvisionOpen(false);
      setFeedback({
        type: "success",
        message: `Field technician ${provisionForm.full_name} provisioned successfully.`,
      });
      await fetchWorkers();
    } catch (err) {
      setProvisionError(err.message || "Failed to provision field worker.");
    } finally {
      setProvisionLoading(false);
    }
  };

  // Editing
  const handleOpenEdit = (worker) => {
    setEditingWorker(worker);
    setEditForm({
      full_name: worker.full_name || "",
      department_id: worker.department_id ? String(worker.department_id) : "",
      designation: worker.designation || "",
      phone_number: worker.phone_number || "",
      employment_status: worker.employment_status || "ACTIVE",
      is_available: Boolean(worker.is_available),
    });
    setEditError(null);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editingWorker) return;
    setEditError(null);

    setEditLoading(true);
    try {
      const payload = {
        full_name: editForm.full_name.trim() || undefined,
        department_id: editForm.department_id ? parseInt(editForm.department_id, 10) : undefined,
        designation: editForm.designation.trim() || undefined,
        phone_number: editForm.phone_number.trim() || undefined,
        employment_status: editForm.employment_status,
        is_available: editForm.is_available,
      };

      await adminService.updateWorker(editingWorker.id, payload);
      setEditingWorker(null);
      setFeedback({
        type: "success",
        message: `Field worker ${editingWorker.full_name || ""} updated successfully.`,
      });
      await fetchWorkers();
    } catch (err) {
      setEditError(err.message || "Failed to update field worker attributes.");
    } finally {
      setEditLoading(false);
    }
  };

  // Deactivation
  const handleDeactivateConfirm = async () => {
    if (!deactivatingWorker) return;
    setDeactivateLoading(true);
    try {
      await adminService.deactivateWorker(deactivatingWorker.id);
      setDeactivatingWorker(null);
      setFeedback({
        type: "success",
        message: `Worker account ${deactivatingWorker.full_name || deactivatingWorker.employee_id} deactivated.`,
      });
      await fetchWorkers();
    } catch (err) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to deactivate worker account.",
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
          <h1 className="portal-header-title">Field Workforce Management</h1>
          <p className="portal-header-subtitle">
            Provision, monitor, and configure municipal field technicians and service personnel.
          </p>
        </div>
        <div className="portal-header-actions">
          <Button variant="primary" onClick={handleOpenProvision}>
            + Provision Field Worker
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

      {/* Workforce Metric Cards */}
      <div className="portal-stats-grid">
        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Total Field Workers
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "var(--color-text-main)" }}>
              {stats.total}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Registered personnel</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Ready for Dispatch
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "#15803d" }}>
              {stats.available}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Active & available now</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              On Leave / Standby
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "#b45309" }}>
              {stats.onLeave}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Temporarily unavailable</span>
          </CardContent>
        </Card>

        <Card>
          <CardContent style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-muted)", fontWeight: "600" }}>
              Deactivated / Inactive
            </span>
            <div style={{ fontSize: "1.75rem", fontWeight: "700", marginTop: "0.25rem", color: "#64748b" }}>
              {stats.inactive}
            </div>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Historical records preserved</span>
          </CardContent>
        </Card>
      </div>

      {/* Filters Bar */}
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
            {/* Search Input */}
            <div style={{ flex: "1 1 240px", maxWidth: "340px" }}>
              <input
                type="text"
                placeholder="Search by worker name, email, badge ID..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                style={{
                  width: "100%",
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              />
            </div>

            {/* Department and Status Selects */}
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <select
                value={selectedDeptId}
                onChange={(e) => {
                  setSelectedDeptId(e.target.value);
                  setPage(1);
                }}
                style={{
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <option value="">All Departments</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.code})
                  </option>
                ))}
              </select>

              <select
                value={selectedStatus}
                onChange={(e) => {
                  setSelectedStatus(e.target.value);
                  setPage(1);
                }}
                style={{
                  padding: "0.5rem 0.75rem",
                  fontSize: "0.875rem",
                  border: "1px solid var(--color-border-card)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <option value="ALL">All Employment Statuses</option>
                <option value="ACTIVE">Active</option>
                <option value="ON_LEAVE">On Leave</option>
                <option value="INACTIVE">Inactive</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Workers Roster Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            Workforce Roster ({filteredWorkers.length} {filteredWorkers.length === 1 ? "technician" : "technicians"})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div style={{ padding: "3rem 0", textAlign: "center" }}>
              <Spinner size="md" message="Loading workforce roster..." />
            </div>
          ) : error ? (
            <Alert variant="error">{error}</Alert>
          ) : displayedWorkers.length === 0 ? (
            <div style={{ padding: "3rem 0", textAlign: "center", color: "var(--color-text-muted)" }}>
              No field workers match the selected criteria.
            </div>
          ) : (
            <>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--color-border-card)", textAlign: "left", color: "var(--color-text-muted)" }}>
                      <th style={{ padding: "0.75rem" }}>Field Worker</th>
                      <th style={{ padding: "0.75rem" }}>Badge ID</th>
                      <th style={{ padding: "0.75rem" }}>Department</th>
                      <th style={{ padding: "0.75rem" }}>Designation</th>
                      <th style={{ padding: "0.75rem" }}>Status</th>
                      <th style={{ padding: "0.75rem" }}>Availability</th>
                      <th style={{ padding: "0.75rem" }}>Registered</th>
                      <th style={{ padding: "0.75rem", textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedWorkers.map((w) => (
                      <tr key={w.id} style={{ borderBottom: "1px solid var(--color-border-card)" }}>
                        <td style={{ padding: "0.75rem" }}>
                          <div style={{ fontWeight: "600", color: "var(--color-text-main)" }}>
                            {w.full_name || "Field Technician"}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                            {w.email}
                            {w.phone_number ? ` \u2022 ${w.phone_number}` : ""}
                          </div>
                        </td>
                        <td style={{ padding: "0.75rem" }}>
                          <code style={{ fontSize: "0.8125rem", padding: "2px 6px", backgroundColor: "var(--color-bg-app)", borderRadius: "var(--radius-sm)" }}>
                            {w.employee_id}
                          </code>
                        </td>
                        <td style={{ padding: "0.75rem" }}>
                          {w.department_name || `Dept #${w.department_id}`}
                        </td>
                        <td style={{ padding: "0.75rem", color: "var(--color-text-muted)" }}>
                          {w.designation || "Field Technician"}
                        </td>
                        <td style={{ padding: "0.75rem" }}>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              fontWeight: "600",
                              padding: "2px 8px",
                              borderRadius: "var(--radius-sm)",
                              backgroundColor:
                                w.employment_status === "ACTIVE"
                                  ? "#dcfce7"
                                  : w.employment_status === "ON_LEAVE"
                                  ? "#fef3c7"
                                  : "#f1f5f9",
                              color:
                                w.employment_status === "ACTIVE"
                                  ? "#15803d"
                                  : w.employment_status === "ON_LEAVE"
                                  ? "#b45309"
                                  : "#475569",
                            }}
                          >
                            {w.employment_status}
                          </span>
                        </td>
                        <td style={{ padding: "0.75rem" }}>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "4px",
                              fontSize: "0.75rem",
                              fontWeight: "600",
                              color: w.is_available ? "#15803d" : "#94a3b8",
                            }}
                          >
                            <span
                              style={{
                                width: "8px",
                                height: "8px",
                                borderRadius: "50%",
                                backgroundColor: w.is_available ? "#22c55e" : "#cbd5e1",
                              }}
                            />
                            {w.is_available ? "Ready" : "Offline"}
                          </span>
                        </td>
                        <td style={{ padding: "0.75rem", whiteSpace: "nowrap", color: "var(--color-text-muted)" }}>
                          {formatDate(w.created_at)}
                        </td>
                        <td style={{ padding: "0.75rem", textAlign: "right" }}>
                          <div style={{ display: "inline-flex", gap: "0.5rem" }}>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenEdit(w)}
                            >
                              Edit
                            </Button>
                            {w.employment_status !== "INACTIVE" && (
                              <Button
                                variant="danger"
                                size="sm"
                                onClick={() => setDeactivatingWorker(w)}
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

              {totalPages > 1 && (
                <div style={{ marginTop: "1.5rem" }}>
                  <Pagination
                    currentPage={page}
                    totalPages={totalPages}
                    onPageChange={setPage}
                  />
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Provision Worker Modal */}
      {isProvisionOpen && (
        <div className="dialog-overlay" role="dialog" aria-modal="true">
          <div className="dialog-backdrop" onClick={() => !provisionLoading && setIsProvisionOpen(false)} />
          <div className="dialog-card" style={{ maxWidth: "540px" }}>
            <h2 className="dialog-title">Provision New Field Worker</h2>
            <p className="dialog-description">
              Create an authenticated User account with the FIELD_WORKER role and register their operational profile.
            </p>

            {provisionError && (
              <div style={{ marginBottom: "1rem" }}>
                <Alert variant="error">{provisionError}</Alert>
              </div>
            )}

            <form onSubmit={handleProvisionSubmit}>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem", margin: "1rem 0" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                    Full Name <span style={{ color: "#e11d48" }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={provisionForm.full_name}
                    onChange={(e) => setProvisionForm({ ...provisionForm, full_name: e.target.value })}
                    placeholder="e.g., Rajesh Sharma"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Email Address <span style={{ color: "#e11d48" }}>*</span>
                    </label>
                    <input
                      type="email"
                      required
                      value={provisionForm.email}
                      onChange={(e) => setProvisionForm({ ...provisionForm, email: e.target.value })}
                      placeholder="worker@municipality.gov"
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Temp Password <span style={{ color: "#e11d48" }}>*</span>
                    </label>
                    <input
                      type="password"
                      required
                      value={provisionForm.password}
                      onChange={(e) => setProvisionForm({ ...provisionForm, password: e.target.value })}
                      placeholder="Min 8 characters"
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Badge / Employee ID <span style={{ color: "#e11d48" }}>*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={provisionForm.employee_id}
                      onChange={(e) => setProvisionForm({ ...provisionForm, employee_id: e.target.value })}
                      placeholder="e.g., TECH-1024"
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Department <span style={{ color: "#e11d48" }}>*</span>
                    </label>
                    <select
                      required
                      value={provisionForm.department_id}
                      onChange={(e) => setProvisionForm({ ...provisionForm, department_id: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    >
                      <option value="">Select Department</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name} ({d.code})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Designation
                    </label>
                    <input
                      type="text"
                      value={provisionForm.designation}
                      onChange={(e) => setProvisionForm({ ...provisionForm, designation: e.target.value })}
                      placeholder="e.g., Road Inspector"
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      value={provisionForm.phone_number}
                      onChange={(e) => setProvisionForm({ ...provisionForm, phone_number: e.target.value })}
                      placeholder="e.g., +91 9876543210"
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>
                </div>
              </div>

              <div className="dialog-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={provisionLoading}
                  onClick={() => setIsProvisionOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={provisionLoading}
                >
                  {provisionLoading ? "Provisioning..." : "Provision Worker"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Worker Modal */}
      {editingWorker && (
        <div className="dialog-overlay" role="dialog" aria-modal="true">
          <div className="dialog-backdrop" onClick={() => !editLoading && setEditingWorker(null)} />
          <div className="dialog-card" style={{ maxWidth: "500px" }}>
            <h2 className="dialog-title">Edit Field Technician Profile</h2>
            <p className="dialog-description">
              Update department assignment, employment standing, and contact profile for {editingWorker.full_name || editingWorker.employee_id}.
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
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={editForm.full_name}
                    onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Department
                    </label>
                    <select
                      value={editForm.department_id}
                      onChange={(e) => setEditForm({ ...editForm, department_id: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    >
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name} ({d.code})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Employment Status
                    </label>
                    <select
                      value={editForm.employment_status}
                      onChange={(e) => setEditForm({ ...editForm, employment_status: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    >
                      <option value="ACTIVE">ACTIVE</option>
                      <option value="ON_LEAVE">ON LEAVE</option>
                      <option value="INACTIVE">INACTIVE</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Designation
                    </label>
                    <input
                      type="text"
                      value={editForm.designation}
                      onChange={(e) => setEditForm({ ...editForm, designation: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.8125rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      value={editForm.phone_number}
                      onChange={(e) => setEditForm({ ...editForm, phone_number: e.target.value })}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-card)" }}
                    />
                  </div>
                </div>

                <div style={{ marginTop: "0.5rem" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.875rem", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={editForm.is_available}
                      onChange={(e) => setEditForm({ ...editForm, is_available: e.target.checked })}
                    />
                    <span>Available for immediate complaint dispatch</span>
                  </label>
                </div>
              </div>

              <div className="dialog-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={editLoading}
                  onClick={() => setEditingWorker(null)}
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

      {/* Deactivate Worker Confirmation Dialog */}
      {deactivatingWorker && (
        <div className="dialog-overlay" role="dialog" aria-modal="true">
          <div className="dialog-backdrop" onClick={() => !deactivateLoading && setDeactivatingWorker(null)} />
          <div className="dialog-card">
            <h2 className="dialog-title" style={{ color: "#e11d48" }}>Deactivate Field Worker Account</h2>
            <p className="dialog-description">
              Are you sure you want to deactivate <strong>{deactivatingWorker.full_name || deactivatingWorker.employee_id}</strong>?
              The worker will be marked inactive and taken offline. All historical assignments, logs, and progress reports will be safely retained.
            </p>

            <div className="dialog-actions">
              <Button
                variant="secondary"
                disabled={deactivateLoading}
                onClick={() => setDeactivatingWorker(null)}
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

export default AdminWorkersPage;
