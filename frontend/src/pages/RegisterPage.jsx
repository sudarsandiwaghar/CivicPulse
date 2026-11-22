import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./AuthPages.css";
import { Card, CardContent } from "../components/Card";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../types/api";

export const RegisterPage = () => {
  const { register, isLoading } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [errors, setErrors] = useState({});
  const [errorMessage, setErrorMessage] = useState(null);
  const [isSuccess, setIsSuccess] = useState(false);

  const validate = () => {
    const errs = {};

    if (!fullName.trim()) {
      errs.fullName = "Full name is required";
    } else if (fullName.trim().length < 2) {
      errs.fullName = "Full name must be at least 2 characters";
    }

    if (!email.trim()) {
      errs.email = "Email address is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errs.email = "Please enter a valid email address";
    }

    if (!password) {
      errs.password = "Password is required";
    } else if (password.length < 8) {
      errs.password = "Password must be at least 8 characters";
    } else if (password.length > 72) {
      errs.password = "Password must be 72 characters or fewer";
    }

    if (!passwordConfirm) {
      errs.passwordConfirm = "Please confirm your password";
    } else if (password !== passwordConfirm) {
      errs.passwordConfirm = "Passwords do not match";
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
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        password_confirm: passwordConfirm,
      });
      setIsSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("An unexpected registration error occurred. Please try again.");
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
          <h1 className="auth-title">Create Citizen Account</h1>
          <p className="auth-subtitle">Join CivicPulse to report municipal issues and track real-time resolution</p>
        </div>

        <Card>
          <CardContent>
            {isSuccess ? (
              <div className="auth-success-box">
                <div className="auth-success-icon">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <h2 style={{ fontSize: "var(--text-xl)", fontWeight: "var(--weight-bold)", color: "var(--color-text-main)", marginBottom: "var(--space-2)" }}>
                  Account Created Successfully
                </h2>
                <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-6)" }}>
                  Your citizen account has been registered. You can now sign in using your email and password.
                </p>
                <Button
                  variant="primary"
                  fullWidth
                  onClick={() => navigate("/login")}
                >
                  Proceed to Sign In
                </Button>
              </div>
            ) : (
              <>
                {errorMessage && (
                  <Alert variant="error" title="Registration Failed">
                    {errorMessage}
                  </Alert>
                )}

                <form onSubmit={handleSubmit} className="auth-form" noValidate>
                  <Input
                    label="Full Name"
                    type="text"
                    required
                    autoComplete="name"
                    placeholder="Enter your full name"
                    value={fullName}
                    onChange={(e) => {
                      setFullName(e.target.value);
                      if (errors.fullName) setErrors((prev) => ({ ...prev, fullName: undefined }));
                    }}
                    error={errors.fullName}
                    disabled={isLoading}
                  />

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
                    autoComplete="new-password"
                    placeholder="Minimum 8 characters"
                    helperText="Must be 8 to 72 characters long"
                    allowPasswordToggle
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                    }}
                    error={errors.password}
                    disabled={isLoading}
                  />

                  <Input
                    label="Confirm Password"
                    type="password"
                    required
                    autoComplete="new-password"
                    placeholder="Confirm your password"
                    allowPasswordToggle
                    value={passwordConfirm}
                    onChange={(e) => {
                      setPasswordConfirm(e.target.value);
                      if (errors.passwordConfirm) setErrors((prev) => ({ ...prev, passwordConfirm: undefined }));
                    }}
                    error={errors.passwordConfirm}
                    disabled={isLoading}
                  />

                  <Button
                    type="submit"
                    variant="primary"
                    fullWidth
                    isLoading={isLoading}
                    disabled={isLoading}
                  >
                    Register Account
                  </Button>
                </form>

                <div className="auth-footer">
                  Already have an account? <Link to="/login">Sign In</Link>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
