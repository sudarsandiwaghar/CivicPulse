/**
 * CivicPulse Geospatial Color Mappings and Configuration
 */

export const STATUS_COLORS = {
  SUBMITTED: "#f59e0b", // Amber
  UNDER_REVIEW: "#0284c7", // Sky Blue
  ASSIGNED: "#9333ea", // Purple
  IN_PROGRESS: "#087f8c", // Teal (CivicPulse primary)
  ON_HOLD: "#ea580c", // Orange
  RESOLVED_AWAITING_VERIFICATION: "#16a34a", // Green
  CLOSED: "#64748b", // Slate Gray
  REJECTED: "#e11d48", // Crimson
  DUPLICATE: "#e11d48",
  REOPENED: "#ec4899", // Rose
};

const envLat = parseFloat(import.meta.env.VITE_MUNICIPAL_DEFAULT_LAT);
const envLng = parseFloat(import.meta.env.VITE_MUNICIPAL_DEFAULT_LNG);
export const HAS_MUNICIPAL_CONFIG = !isNaN(envLat) && !isNaN(envLng);

// When municipal environment coordinates are configured, use them.
// When unconfigured, provide a neutral national overview without assuming or fabricating a specific deployment city.
export const DEFAULT_MUNICIPAL_CENTER = HAS_MUNICIPAL_CONFIG
  ? [envLat, envLng]
  : [20.5937, 78.9629];

export const DEFAULT_MAP_ZOOM = HAS_MUNICIPAL_CONFIG ? 13 : 5;
export const DEFAULT_MUNICIPAL_CITY = import.meta.env.VITE_MUNICIPAL_CITY || "";
