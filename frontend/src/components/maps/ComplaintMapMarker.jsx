import L from "leaflet";
import { STATUS_COLORS } from "./mapConstants";
import "./ComplaintMap.css";

/**
 * Validate geographic coordinates within standard WGS84 bounds.
 */
export function isValidCoordinate(lat, lng) {
  if (lat === null || lat === undefined || lng === null || lng === undefined) {
    return false;
  }
  const numLat = Number(lat);
  const numLng = Number(lng);
  if (isNaN(numLat) || isNaN(numLng)) {
    return false;
  }
  if (!isFinite(numLat) || !isFinite(numLng)) {
    return false;
  }
  return numLat >= -90.0 && numLat <= 90.0 && numLng >= -180.0 && numLng <= 180.0;
}

/**
 * Create a custom colored Leaflet HTML pin icon based on complaint status.
 */
export function createStatusIcon(status = "SUBMITTED") {
  const color = STATUS_COLORS[status] || "#087f8c";
  return L.divIcon({
    className: "custom-map-marker-container",
    html: `
      <div class="custom-map-pin" style="background-color: ${color};">
        <div class="custom-map-pin-inner"></div>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -28],
  });
}

/**
 * Create a custom location picker pin (pulsing / draggable).
 */
export function createPickerIcon() {
  return L.divIcon({
    className: "custom-map-marker-container",
    html: `
      <div class="custom-map-pin" style="background-color: #087f8c; transform: rotate(-45deg) scale(1.15);">
        <div class="custom-map-pin-inner"></div>
      </div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 36],
    popupAnchor: [0, -32],
  });
}

