import React from "react";
import "./Table.css";

export function Table({
  columns,
  data,
  keyExtractor,
  emptyMessage = "No records found.",
  className = "",
}) {
  return (
    <div className={`table-responsive ${className}`}>
      <table className="table-custom">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={col.width ? { width: col.width } : undefined}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="table-empty">
                <div className="table-empty-icon">📁</div>
                <div>{emptyMessage}</div>
              </td>
            </tr>
          ) : (
            data.map((row, index) => (
              <tr key={keyExtractor(row, index)}>
                {columns.map((col) => (
                  <td key={col.key}>
                    {col.render ? col.render(row, index) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
