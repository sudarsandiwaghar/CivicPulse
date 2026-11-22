"""
CivicPulse Test Suite Package

Contains all tests for the CivicPulse application, organised by domain.
Uses pytest as the test framework with fixtures defined in conftest.py.

Test categories:
    - Unit tests: Test individual functions and service methods in isolation.
    - Integration tests: Test API endpoints with a real database session.
    - Security tests: Verify authentication, authorisation, and input validation.

Running tests:
    pytest                      # Run all tests
    pytest -v                   # Verbose output
    pytest tests/test_health.py # Run specific test file
    pytest -k "test_health"     # Run tests matching a pattern
"""
