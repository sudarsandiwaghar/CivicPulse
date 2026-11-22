"""
CivicPulse Application Package

Root package for the CivicPulse civic issue reporting and intelligence
platform. This package contains the FastAPI application factory, all API
routes, database models, business logic services, and core utilities.

Package Structure:
    api/        — API route definitions (versioned)
    core/       — Cross-cutting concerns (security, exceptions, constants)
    db/         — Database engine, session management, declarative base
    models/     — SQLAlchemy ORM model definitions
    schemas/    — Pydantic request/response schemas
    services/   — Business logic and service layer
    ai/         — AI/ML processing modules (future phases)
"""
