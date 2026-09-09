# Business Requirements

## Vision

Ground Zero is a modular platform core enabling multiple recruiting intelligence agents to be deployed on AWS without requiring platform modifications.

## Stakeholders

- **Candidates**: Upload CVs, receive job matches
- **Recruiters**: Search candidates, manage positions
- **Platform Admins**: Deploy and manage agents, monitor system
- **System Developers**: Build and maintain agents and platform components

## Core Requirements

### R1: Modularity
- New agents can be added without modifying the platform core
- Agent interfaces are standardized through contracts
- Agents can be independently versioned and deployed

### R2: Scalability
- Horizontal scaling of individual agents
- Independent scaling per agent workload
- Asynchronous processing via SQS

### R3: Security
- User authentication via Cognito (JWT-based)
- Role-based access control (Candidate, Recruiter, Company Admin, Platform Admin, Service)
- Least privilege IAM policies
- Multi-tenant data isolation

### R4: Reliability
- Exactly-once business outcomes (despite at-least-once delivery)
- Idempotency protection for all operations
- Retry mechanisms with exponential backoff
- Dead letter queue for failed processing

### R5: Observability
- Structured logging to CloudWatch
- Metrics for agent performance and system health
- Alerting on errors and anomalies
- Dashboards for operational visibility

### R6: Environment Management
- DEV → TEST → PROD deployment pipeline
- Isolated environments per environment
- Controlled deployments with approvals

### R7: Cost Efficiency
- Use serverless services (pay-per-use)
- Free tier utilization where possible
- Cost monitoring and alerting

## Non-Functional Requirements

- **Latency**: API responses < 1 second for user-facing operations
- **Availability**: 99.9% uptime for core services
- **Scalability**: Support from 1 to 1000+ concurrent workers
- **Maintainability**: Terrabyte configuration, automated testing
- **Portability**: Avoid vendor lock-in where possible (open standards)

## Out of Scope

- Specific recruiting agent logic (CV processing, ATS, matching algorithms)
- Frontend user interfaces
- Downstream integrations beyond standard APIs

## Assumptions

- AWS is the target cloud provider
- Serverless architecture preferred over containers/virtual machines
- Python 3.14 as runtime for Lambda functions
- Terraform as IaC tool