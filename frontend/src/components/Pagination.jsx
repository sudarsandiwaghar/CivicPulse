import React from "react";
import "./Pagination.css";

export const Pagination = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  className = "",
}) => {
  if (totalPages <= 1) return null;

  const startItem = totalItems !== undefined && pageSize !== undefined
    ? (currentPage - 1) * pageSize + 1
    : undefined;
  const endItem = totalItems !== undefined && pageSize !== undefined
    ? Math.min(currentPage * pageSize, totalItems)
    : undefined;

  return (
    <div className={`pagination ${className}`}>
      <div>
        {startItem !== undefined && endItem !== undefined && totalItems !== undefined ? (
          <span>
            Showing <strong>{startItem}</strong> to <strong>{endItem}</strong> of <strong>{totalItems}</strong> entries
          </span>
        ) : (
          <span>
            Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
          </span>
        )}
      </div>
      <div className="pagination-controls">
        <button
          type="button"
          className="pagination-btn"
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
          aria-label="Previous Page"
        >
          &larr; Prev
        </button>
        <span className="pagination-btn active">{currentPage}</span>
        <button
          type="button"
          className="pagination-btn"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          aria-label="Next Page"
        >
          Next &rarr;
        </button>
      </div>
    </div>
  );
};
