import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import "./AuthPages.css";
import { Card, CardContent } from "../components/Card";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../types/api";

export const LoginPage = () => {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [errorMessage, setErrorMessage] = useState(null);

  const validate = () => {
    const errs = {};

    if (!email.trim()) {
      errs.email = "Email address is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errs.email = "Please enter a valid email address";
    }

    if (!password) {
      errs.password = "Password is required";
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!validate()) {
      return;
    }

    try {
      const user = await login({ email: email.trim(), password });

      // Determine redirect destination
      const from = location.state?.from?.pathname;
      if (from) {
        navigate(from, { replace: true });
        return;
      }

      // Default role routing
      switch (user.role) {
        case "ADMINISTRATOR":
          navigate("/admin", { replace: true });
          break;
        case "FIELD_WORKER":
          navigate("/worker", { replace: true });
          break;
        case "CITIZEN":
        default:
          navigate("/citizen", { replace: true });
          break;
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("An unexpected authentication error occurred. Please try again.");
      }
    }
  };

  return (
    <div className="auth-page-wrapper">
      <div className="auth-card-container">
        <div className="auth-header">
          <Link to="/" className="auth-brand-badge">
            <div className="auth-brand-icon">CP</div>
            <div className="auth-brand-name">
              Civic<span>Pulse</span>
            </div>
          </Link>
          <h1 className="auth-title">Welcome Back</h1>
          <p className="auth-subtitle">Sign in to access your civic account and operational queues</p>
        </div>

        <Card>
          <CardContent>
            {errorMessage && (
              <Alert variant="error" title="Sign In Failed">
                {errorMessage}
              </Alert>
            )}

            <form onSubmit={handleSubmit} className="auth-form" noValidate>
              <Input
                label="Email Address"
                type="email"
                required
                autoComplete="email"
                placeholder="citizen@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
                }}
                error={errors.email}
                disabled={isLoading}
              />

              <Input
                label="Password"
                type="password"
                required
                autoComplete="current-password"
                placeholder="Enter your password"
                allowPasswordToggle
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                }}
                error={errors.password}
                disabled={isLoading}
              />

              <Button
                type="submit"
                variant="primary"
                fullWidth
                isLoading={isLoading}
                disabled={isLoading}
              >
                Sign In
              </Button>
            </form>

            <div className="auth-footer">
              Don't have an account? <Link to="/register">Register here</Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
