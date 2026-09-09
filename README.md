# Mays Recruiting Intelligence System

Ground Zero - Modular Platform Core for Recruiting Intelligence Agents

## Overview

This repository contains the Ground Zero platform foundation for the Mays Recruiting Intelligence System. The platform provides a standardized, scalable, and secure foundation for deploying multiple recruiting agents (CV processing, ATS, matching, etc.).

**Key Distinction:** Ground Zero is NOT the individual recruiting agents. It is the platform core that enables agents to be added as modular slots.

## Architecture

```text
                    GROUND ZERO
                         │
 ┌───────────────────────┼────────────────────────┐
 │                       │                        │
 ▼                       ▼                        ▼
AUTH                    WORK                     DATA
Cognito                 SQS                      DynamoDB
IAM                     WorkItem                 S3
                         Idempotency
 │                       │                        │
 └───────────────────────┼────────────────────────┘
                         ▼
                    AGENT RUNTIME
                         │
              +++++++++++│+++++++++++
              +          │          +
              +      AGENT SLOT     +
              +          │          +
              +++++++++++│+++++++++++
                         │
                ┌────────┼────────┐
                ▼        ▼        ▼
               CV       ATS      MATCH
```

## Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| Auth | User & tenant authentication | Amazon Cognito |
| Work System | Asynchronous job processing | SQS + Lambda |
| Data Layer | Persistent storage | DynamoDB + S3 |
| Agent Runtime | Modular agent execution | Lambda |
| Observability | Monitoring & alerting | CloudWatch |

## Getting Started

1. Review requirements in `requirements/`
2. Read architecture overview in `architecture/`
3. Explore agent contracts in `agents/`
4. Review terraform setup in `terraform/`

## Indices

- [Architecture Overview](architecture/ground-zero.md)
- [Agent Contract](agents/agent-contract.md)
- [Agent Matrix](agents/agent-matrix.md)
- [Work Item Model](work-system/work-item.md)
- [Architecture Decisions](architecture/architecture-decisions.md)