# CivicPulse — AI/ML Documentation

## Overview

CivicPulse integrates artificial intelligence and machine learning to enhance civic complaint processing. AI provides **recommendations** to administrators — it never makes autonomous decisions.

## Current Status

**Phase 1** — Package structure created (`app/ai/`). No models implemented yet.

AI/ML development begins in **Phase 12** after the core backend is stable and reliable.

## Planned Capabilities

| Capability | Input | Output | Phase |
|---|---|---|---|
| Image Classification | Complaint photo | Issue type prediction + confidence | Phase 12 |
| Text Classification | Complaint description | Category suggestion + confidence | Phase 12 |
| Duplicate Detection | New complaint | Similar existing complaints + scores | Phase 12 |
| Severity Prediction | Complaint text + metadata | Priority recommendation + confidence | Phase 12 |
| Geographic Hotspot Analysis | Complaint locations | Cluster identification + heatmap data | Phase 12 |
| Multilingual Processing | Complaint in any language | Translated + classified complaint | Phase 12 |
| Predictive Analytics | Historical complaint data | Trend forecasts | Phase 12 |

## Design Principles

1. **Recommendations, not decisions** — AI outputs are suggestions presented to admins for review.
2. **Confidence scores** — Every prediction includes a confidence score (0.0 to 1.0) with interpretation guidance.
3. **Auditability** — All AI assessments are stored in the `ai_assessments` table with full provenance.
4. **Graceful degradation** — The platform functions fully without AI services; they are an enhancement, not a dependency.
5. **No fabricated accuracy** — Model accuracy claims require actual evaluation against labelled test data.

## Architecture

*Detailed architecture, model specifications, training methodology, and evaluation results will be documented when Phase 12 is implemented.*

## AI Assessment Storage

Each AI assessment will record:
- Complaint ID
- Assessment type (classification, duplicate, severity, etc.)
- Prediction result
- Confidence score
- Model version
- Processing timestamp
- Explanation text (human-readable reasoning)
