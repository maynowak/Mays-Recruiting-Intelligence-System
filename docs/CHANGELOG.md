# Changelog

All notable changes to the Ground Zero platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [G2.8] - 2026-09-13

### Added
- InvocationContract for agent-to-agent calls
- AgentInvoker class for execution
- invoke_agent() convenience function
- SYNC/ASYNC mode support
- Parent work ID for traceability

### Changed
- Added agent invocation abstraction to Agent Body

## [G2.7] - 2026-09-12

### Added
- Worker Lambda now uses Agent Body executor
- `_process_work_item()` calls AgentBody.execute()
- Graceful fallback mode for deployment safety
- Result includes workId, workType, status, agentType

### Changed
- Wired Agent Body into the SQS work processing flow

## [G0.5] - 2026-09-10

### Added
- Agent Base contract (AgentBase class)
- Reference Agent implementation
- Agent handler template
- Agent contract documentation
- Agent evaluation matrix

## [G2.5] - 2026-09-12

### Added
- Agent Body Router for work item routing
- Agent Body Context for execution context extraction
- Agent Body Executor for lifecycle management
- Agent Body Result Handler for standardized output
- Agent Body Monitor for observability
- Agent Body integration with Reference Agent
- Architecture guide for Agent Body and Runtime

### Changed
- Fixed Agent Body handler signature for Ground Zero compatibility

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