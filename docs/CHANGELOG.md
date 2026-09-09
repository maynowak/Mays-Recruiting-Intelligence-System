# Changelog

All notable changes to the Ground Zero platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [G0.2] - 2026-09-09

### Added
- Complete Terraform infrastructure for Ground Zero platform
- API Gateway HTTP API V2 with JWT authentication
- SQS work queues (work, CV, ATS, Match queues) with DLQ
- DynamoDB tables for work items and agent state
- Cognito user pool for authentication
- Lambda function with SQS event source mapping
- IAM least privilege policies
- S3 bucket for data storage with encryption
- CloudWatch monitoring with alarms
- GitHub Actions CI/CD workflow
- Python requirements for development
- Agent base class and handler template
- WorkItem lifecycle documentation
- DEV/TEST/PROD environment strategy

### Changed
- Consolidated all infrastructure as code into Terraform modules
- Standardized agent interface contract

## [G0.1] - 2026-09-09

### Added
- Initial project structure
- Business and technical requirements documentation
- Architecture documentation (ground-zero.md)
- Architecture Decision Records
- Agent contract specification
- Agent evaluation matrix
- WorkItem lifecycle documentation
- DEV/TEST/PROD strategy documentation
- README with platform overview