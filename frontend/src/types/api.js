/**
 * CivicPulse API Error Class
 * Runtime error class representing HTTP API errors with status code and payload.
 */

export class ApiError extends Error {
  constructor(statusCode, message, errorData) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.errorData = errorData;
  }
}
