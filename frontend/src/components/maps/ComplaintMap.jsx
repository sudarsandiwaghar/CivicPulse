import React, { useEffect, useRef, useMemo } from "react";
import L from "leaflet";
import "./ComplaintMap.css";
import { isValidCoordinate, createStatusIcon } from "./ComplaintMapMarker";
import { DEFAULT_MUNICIPAL_CENTER, DEFAULT_MAP_ZOOM } from "./mapConstants";
import { MapLegend } from "./MapLegend";
import { MapLoadingState } from "./MapLoadingState";

export const ComplaintMap = ({
  complaints = [],
  selectedComplaintId = null,
  onSelectComplaint = null,
  center = DEFAULT_MUNICIPAL_CENTER,
  zoom = DEFAULT_MAP_ZOOM,
  height = "480px",
  showLegend = true,
  userRole = "CITIZEN",
  isLoading = false,
  emptyMessage = "No location coordinates recorded for selected complaints.",
}) => {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersLayerRef = useRef(null);
  const initialCenterRef = useRef(center);
  const initialZoomRef = useRef(zoom);

  // Filter complaints that possess valid coordinates
  const validComplaints = useMemo(() => {
    return complaints.filter((c) => {
      const lat = c.location?.latitude;
      const lng = c.location?.longitude;
      return isValidCoordinate(lat, lng);
    });
  }, [complaints]);

  // Aggregate counts for legend
  const statusCounts = useMemo(() => {
    const counts = {};
    validComplaints.forEach((c) => {
      counts[c.status] = (counts[c.status] || 0) + 1;
    });
    return counts;
  }, [validComplaints]);

  // Initialize Map Instance
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: initialCenterRef.current,
        zoom: initialZoomRef.current,
        zoomControl: true,
        scrollWheelZoom: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);

      const markersGroup = L.layerGroup().addTo(map);
      markersLayerRef.current = markersGroup;
      mapInstanceRef.current = map;

      // Handle resize
      const timer = setTimeout(() => {
        map.invalidateSize();
      }, 150);

      return () => {
        clearTimeout(timer);
        map.remove();
        mapInstanceRef.current = null;
        markersLayerRef.current = null;
      };
    }
  }, []);

  // Update Markers when validComplaints change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    if (!map || !markersGroup) return;

    markersGroup.clearLayers();

    if (validComplaints.length === 0) return;

    const bounds = L.latLngBounds();

    validComplaints.forEach((c) => {
      const lat = Number(c.location.latitude);
      const lng = Number(c.location.longitude);
      const latLng = [lat, lng];
      bounds.extend(latLng);

      const icon = createStatusIcon(c.status);
      const marker = L.marker(latLng, { icon });

      // Determine dossier URL
      let dossierUrl = `/citizen/complaints/${c.id}`;
      if (userRole === "ADMINISTRATOR") {
        dossierUrl = `/admin/complaints/${c.id}`;
      } else if (userRole === "FIELD_WORKER") {
        dossierUrl = `/worker/tasks`;
      }

      // Build popup markup
      const popupHtml = `
        <div class="map-popup-card">
          <div class="map-popup-header">
            <span style="font-size: 0.6875rem; font-weight: 700; color: #087f8c;">
              ${c.complaint_number}
            </span>
            <span style="font-size: 0.6875rem; font-weight: 600; text-transform: uppercase;">
              ${c.priority || ""}
            </span>
          </div>
          <h4 class="map-popup-title">${c.title || "Complaint"}</h4>
          <div class="map-popup-meta">
            <span><strong>Status:</strong> ${c.status}</span>
            <span><strong>Category:</strong> ${c.category_name || "Uncategorized"}</span>
            <span><strong>Ward/Area:</strong> ${c.location.area_name || c.location.city || "Area on file"}</span>
          </div>
          <a href="${dossierUrl}" class="map-popup-action">
            Inspect Complaint Dossier &rarr;
          </a>
        </div>
      `;

      marker.bindPopup(popupHtml);

      marker.on("click", () => {
        if (onSelectComplaint) {
          onSelectComplaint(c);
        }
      });

      markersGroup.addLayer(marker);

      // Auto-open if selected
      if (selectedComplaintId && c.id === selectedComplaintId) {
        marker.openPopup();
      }
    });

    // Fit map bounds
    if (validComplaints.length > 1) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    } else if (validComplaints.length === 1) {
      map.setView([validComplaints[0].location.latitude, validComplaints[0].location.longitude], 14);
    }
  }, [validComplaints, selectedComplaintId, onSelectComplaint, userRole]);

  return (
    <div className="map-wrapper" style={{ height }}>
      {isLoading && <MapLoadingState message="Rendering geographic markers..." />}

      {!isLoading && validComplaints.length === 0 && (
        <div
          style={{
            position: "absolute",
            top: "1rem",
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "rgba(255, 255, 255, 0.95)",
            padding: "0.5rem 1rem",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border-card)",
            fontSize: "0.8125rem",
            color: "var(--color-text-muted)",
            zIndex: 500,
            boxShadow: "var(--shadow-sm)",
          }}
        >
          {emptyMessage}
        </div>
      )}

      <div ref={mapContainerRef} className="map-container" />

      {showLegend && <MapLegend counts={statusCounts} />}
    </div>
  );
};

export default ComplaintMap;
