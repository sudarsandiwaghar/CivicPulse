import React from "react";
import { Spinner } from "../Spinner";
import "./ComplaintMap.css";

export const MapLoadingState = ({ message = "Loading geographic map..." }) => {
  return (
    <div className="map-loading-overlay">
      <Spinner size="md" />
      <span>{message}</span>
    </div>
  );
};

export default MapLoadingState;
