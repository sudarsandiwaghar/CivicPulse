import React, { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import "./ComplaintMap.css";
import { isValidCoordinate, createPickerIcon } from "./ComplaintMapMarker";
import { DEFAULT_MUNICIPAL_CENTER, DEFAULT_MAP_ZOOM } from "./mapConstants";
import { Button } from "../Button";
import { Spinner } from "../Spinner";

export const LocationPicker = ({
  latitude,
  longitude,
  onLocationChange,
  height = "340px",
  disabled = false,
}) => {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markerRef = useRef(null);

  const [isLocating, setIsLocating] = useState(false);
  const [geoNotice, setGeoNotice] = useState(null);

  // Parse current coordinates safely
  const currentLat = parseFloat(latitude);
  const currentLng = parseFloat(longitude);
  const hasValidCoords = isValidCoordinate(currentLat, currentLng);

  // Callback wrapper for location updates
  const handleCoordChange = useCallback(
    (lat, lng) => {
      if (disabled || !onLocationChange) return;
      onLocationChange({
        latitude: lat.toFixed(6),
        longitude: lng.toFixed(6),
      });
    },
    [disabled, onLocationChange]
  );

  const coordChangeRef = useRef(handleCoordChange);
  const disabledRef = useRef(disabled);

  useEffect(() => {
    coordChangeRef.current = handleCoordChange;
    disabledRef.current = disabled;
  }, [handleCoordChange, disabled]);

  // Helper to attach or move marker
  const setOrUpdateMarker = useCallback((lat, lng, map) => {
    const activeMap = map || mapInstanceRef.current;
    if (!activeMap) return;

    if (!markerRef.current) {
      const marker = L.marker([lat, lng], {
        draggable: !disabledRef.current,
        icon: createPickerIcon(),
      }).addTo(activeMap);

      marker.bindPopup("<strong>Incident Location</strong><br/>Drag or click to adjust").openPopup();

      marker.on("dragend", (e) => {
        const pos = e.target.getLatLng();
        coordChangeRef.current?.(pos.lat, pos.lng);
      });

      markerRef.current = marker;
    } else {
      markerRef.current.setLatLng([lat, lng]);
    }
  }, []);

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const initCenter = hasValidCoords
        ? [currentLat, currentLng]
        : DEFAULT_MUNICIPAL_CENTER;
      const initZoom = hasValidCoords ? 15 : DEFAULT_MAP_ZOOM;

      const map = L.map(mapContainerRef.current, {
        center: initCenter,
        zoom: initZoom,
        zoomControl: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);

      // If valid coords were passed initially, create marker
      if (hasValidCoords) {
        setOrUpdateMarker(currentLat, currentLng, map);
      }

      // Listen for map click to place or move marker
      map.on("click", (e) => {
        if (disabledRef.current) return;
        const { lat, lng } = e.latlng;
        setOrUpdateMarker(lat, lng, map);
        coordChangeRef.current?.(lat, lng);
      });

      mapInstanceRef.current = map;

      // Invalidate size to ensure clean rendering
      const timer = setTimeout(() => {
        map.invalidateSize();
      }, 150);

      return () => {
        clearTimeout(timer);
        map.remove();
        mapInstanceRef.current = null;
        markerRef.current = null;
      };
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Update marker when external lat/lng changes
  useEffect(() => {
    const marker = markerRef.current;
    const map = mapInstanceRef.current;
    if (!map) return;

    if (hasValidCoords) {
      if (!marker) {
        setOrUpdateMarker(currentLat, currentLng, map);
      } else {
        const currentPos = marker.getLatLng();
        if (
          Math.abs(currentPos.lat - currentLat) > 0.00001 ||
          Math.abs(currentPos.lng - currentLng) > 0.00001
        ) {
          marker.setLatLng([currentLat, currentLng]);
          map.panTo([currentLat, currentLng]);
        }
      }
    } else if (marker) {
      // If coordinates cleared externally, remove pin
      marker.remove();
      markerRef.current = null;
    }
  }, [currentLat, currentLng, hasValidCoords, setOrUpdateMarker]);

  // Handle GPS detection
  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      setGeoNotice({
        type: "error",
        text: "Geolocation is not supported by your browser. Please select location manually on the map.",
      });
      return;
    }

    setIsLocating(true);
    setGeoNotice(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        setIsLocating(false);
        setGeoNotice({
          type: "success",
          text: `Current GPS position detected (${lat.toFixed(4)}, ${lng.toFixed(4)}).`,
        });

        if (mapInstanceRef.current) {
          setOrUpdateMarker(lat, lng, mapInstanceRef.current);
          mapInstanceRef.current.flyTo([lat, lng], 16, { animate: true });
        }
        handleCoordChange(lat, lng);
      },
      (err) => {
        setIsLocating(false);
        let errorMsg = "Unable to retrieve GPS coordinates.";
        if (err.code === 1) {
          errorMsg = "Location permission denied. Please click on the map to pinpoint the incident location.";
        } else if (err.code === 2) {
          errorMsg = "Position unavailable. Please click on the map manually.";
        } else if (err.code === 3) {
          errorMsg = "Location request timed out. Please click on the map manually.";
        }
        setGeoNotice({ type: "error", text: errorMsg });
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  // Reset to neutral municipal view / unpin
  const handleReset = () => {
    if (markerRef.current && mapInstanceRef.current) {
      markerRef.current.remove();
      markerRef.current = null;
      mapInstanceRef.current.flyTo(DEFAULT_MUNICIPAL_CENTER, DEFAULT_MAP_ZOOM);
    }
    if (onLocationChange) {
      onLocationChange({ latitude: "", longitude: "" });
    }
    setGeoNotice(null);
  };

  return (
    <div className="location-picker-wrapper" style={{ width: "100%", marginBottom: "var(--space-4)" }}>
      {/* Control Toolbar */}
      <div className="location-picker-toolbar">
        <div className="location-picker-coords">
          <span>Target Coordinates:</span>
          <span className="coords-badge">
            {hasValidCoords
              ? `${currentLat.toFixed(6)}, ${currentLng.toFixed(6)}`
              : "No location selected"}
          </span>
        </div>

        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleDetectLocation}
            disabled={disabled || isLocating}
          >
            {isLocating ? (
              <>
                <Spinner size="sm" />
                <span style={{ marginLeft: "var(--space-2)" }}>Detecting GPS...</span>
              </>
            ) : (
              <>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ marginRight: 6 }}
                >
                  <circle cx="12" cy="12" r="10" />
                  <polygon points="12 2 15 8 12 14 9 8 12 2" />
                </svg>
                Use My Current Location
              </>
            )}
          </Button>

          {hasValidCoords && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={disabled || isLocating}
              title="Clear pinned location"
            >
              Clear Pin
            </Button>
          )}
        </div>
      </div>

      {/* Geolocation Notice Banner */}
      {geoNotice && (
        <div
          style={{
            padding: "var(--space-2) var(--space-4)",
            fontSize: "var(--text-xs)",
            backgroundColor:
              geoNotice.type === "success"
                ? "var(--color-bg-active-nav)"
                : "rgba(224, 49, 49, 0.08)",
            color:
              geoNotice.type === "success"
                ? "var(--color-primary)"
                : "var(--color-danger)",
            borderBottom: "1px solid var(--color-border-card)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>{geoNotice.text}</span>
          <button
            type="button"
            onClick={() => setGeoNotice(null)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "1rem",
              lineHeight: 1,
              color: "inherit",
            }}
          >
            &times;
          </button>
        </div>
      )}

      {/* Leaflet Map Frame */}
      <div className="map-wrapper" style={{ height }}>
        <div ref={mapContainerRef} className="map-container" />
      </div>

      {/* Helpful Hint */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          marginTop: "var(--space-2)",
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
        }}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>
          Click directly on the map or drag the marker to pinpoint the exact location of the civic incident.
        </span>
      </div>
    </div>
  );
};

export default LocationPicker;
