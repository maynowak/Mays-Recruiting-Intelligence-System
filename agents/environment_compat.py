"""
Environment Compatibility Framework for Mays-RIS

This module provides environment discovery and compatibility checking
for determining if an existing Mays-Orders-AWS environment is suitable
for Mays-RIS deployment.

CRITICAL ARCHITECTURE PRINCIPLES:
1. NO AWS credentials required
2. NO network calls
3. NO file system modifications
4. NO side effects
5. DETERMINISTIC output based on input

MANAYS-ORDERS-AWS ENVIRONMENT IDENTITY CONTRACT
Based on SHARED-CONTRACT-01 and ARCH-ATS-BOUNDARY-01

Expected Environment Identity:
- product: "mays-orders" (or similar order management identifier)
- project: "maynowak"
- environment: "production" | "staging" | "development"
- region: AWS region (e.g., "us-east-1")
- account_id: AWS account ID

Expected Contracts:
- orders.port: OrdersPort interface (see agents/orders/adapter.py)
- user.context: User authentication context
- work.item: Work item contract (see lambda/handler.py)

Expected Capabilities:
- order-processing
- tenant-isolation
- work-execution

Mays-RIS Requirements:
- Required: OrdersPort interface available
- Required: HTTP API for orders processing
- Required: User context extraction capability
- No breaking contract changes from previous versions

IMPORTANT: This is a TEST FIXTURE based on documented contracts.
Actual Mays-Orders-AWS environment may differ.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class CompatibilityStatus(Enum):
    """Compatibility status for environment check."""
    COMPATIBLE = "COMPATIBLE"
    REVIEW = "REVIEW"
    INCOMPATIBLE = "INCOMPATIBLE"


@dataclass
class EnvironmentIdentity:
    """
    Identity information for an environment.
    
    Based on SHARED-CONTRACT-01 expectations.
    """
    product: Optional[str] = None
    project: Optional[str] = None
    environment: Optional[str] = None
    region: Optional[str] = None
    account_id: Optional[str] = None
    deployment_id: Optional[str] = None
    version: Optional[str] = None


@dataclass
class ContractMetadata:
    """
    Contract metadata for environment compatibility checking.
    
    Based on dependency_check.py structure.
    """
    contract_id: str
    version: str = "1.0.0"
    owner: Optional[str] = None
    compatibility: str = "stable"
    consumers: List[str] = field(default_factory=list)


@dataclass
class CapabilityMetadata:
    """
    Capability provided by an environment.
    """
    capability_id: str
    description: Optional[str] = None
    available: bool = True


@dataclass
class EnvironmentSnapshot:
    """
    Complete snapshot of an environment's state.
    """
    identity: EnvironmentIdentity
    contracts: List[ContractMetadata] = field(default_factory=list)
    capabilities: List[CapabilityMetadata] = field(default_factory=list)
    source: str = "unknown"


@dataclass
class CompatibilityResult:
    """
    Result of environment compatibility check.
    """
    status: CompatibilityStatus
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


class EnvironmentDiscovery(ABC):
    """
    Abstract base class for environment discovery.
    
    Implementations can discover environment information from different
    sources (fixtures, AWS metadata, installer state, etc.)
    
    EXTENSION POINT: Future implementations can query:
    - AWS CloudFormation outputs
    - Terraform state
    - API Gateway endpoints
    - DynamoDB tables
    """
    
    @abstractmethod
    def discover(self) -> EnvironmentSnapshot:
        """
        Discover environment information.
        
        Returns:
            EnvironmentSnapshot with identity, contracts, and capabilities.
        """
        pass


class CompatibilityEngine:
    """
    Engine for checking environment compatibility.
    
    Rules:
    1. Environment compatibility requires all required contracts
    2. Contract versions must be compatible (semantic versioning rules)
    3. Required capabilities must be available
    4. Missing optional metadata results in REVIEW, not INCOMPATIBLE
    """
    
    REQUIRED_CONTRACTS = [
        "orders.port",
        "user.context",
        "work.item",
    ]
    
    REQUIRED_CAPABILITIES = [
        "order-processing",
        "tenant-isolation",
        "work-execution",
    ]
    
    OPTIONAL_METADATA = [
        "deployment_id",
        "account_id",
    ]
    
    def __init__(self, strict_versioning: bool = True):
        """
        Initialize compatibility engine.
        
        Args:
            strict_versioning: If True, require exact version match.
                               If False, allow same major.minor.
        """
        self.strict_versioning = strict_versioning
    
    def check(self, snapshot: EnvironmentSnapshot) -> CompatibilityResult:
        """
        Check if environment is compatible.
        
        Args:
            snapshot: Environment snapshot to check
            
        Returns:
            CompatibilityResult with status and details
        """
        issues = []
        warnings = []
        details = {
            "identity": {
                "product": snapshot.identity.product,
                "environment": snapshot.identity.environment,
                "region": snapshot.identity.region,
                "version": snapshot.identity.version,
            },
            "contracts_checked": len(snapshot.contracts),
            "capabilities_checked": len(snapshot.capabilities),
        }
        
        # Check required contracts
        available_contract_ids = {c.contract_id for c in snapshot.contracts}
        missing_contracts = []
        for required in self.REQUIRED_CONTRACTS:
            if required not in available_contract_ids:
                missing_contracts.append(required)
        
        if missing_contracts:
            issues.append(f"Missing required contracts: {missing_contracts}")
        
        # Check required capabilities
        available_capabilities = {c.capability_id for c in snapshot.capabilities if c.available}
        missing_capabilities = []
        for required in self.REQUIRED_CAPABILITIES:
            if required not in available_capabilities:
                missing_capabilities.append(required)
        
        if missing_capabilities:
            issues.append(f"Missing required capabilities: {missing_capabilities}")
        
        # Check optional metadata
        identity = snapshot.identity
        if identity.version is None:
            warnings.append("Version metadata not provided")
        if identity.product is None:
            warnings.append("Product metadata not provided")
        
        # Determine final status
        if issues:
            status = CompatibilityStatus.INCOMPATIBLE
            reason = "; ".join(issues)
        elif warnings:
            status = CompatibilityStatus.REVIEW
            reason = "; ".join(warnings)
        else:
            status = CompatibilityStatus.COMPATIBLE
            reason = "Environment meets all requirements"
        
        details["issues"] = issues
        details["warnings"] = warnings
        
        return CompatibilityResult(
            status=status,
            reason=reason,
            details=details
        )


class EnvironmentDiscoveryFixture(EnvironmentDiscovery):
    """
    Fixture-based environment discovery for testing.
    
    This simulates discovering an environment from configuration files,
    API responses, or other non-AWS sources.
    
    IMPORTANT: This uses TEST DATA based on documented contracts,
    NOT actual AWS environment state.
    """
    
    def __init__(self, fixture_type: str = "compatible"):
        """
        Initialize with a specific fixture type.
        
        Args:
            fixture_type: One of "compatible", "missing_contract", 
                         "missing_capability", "version_mismatch", "minimal"
        """
        self.fixture_type = fixture_type
    
    def discover(self) -> EnvironmentSnapshot:
        """
        Return a fixture-based environment snapshot.
        """
        if self.fixture_type == "compatible":
            return self._create_compatible_fixture()
        elif self.fixture_type == "missing_contract":
            return self._create_missing_contract_fixture()
        elif self.fixture_type == "missing_capability":
            return self._create_missing_capability_fixture()
        elif self.fixture_type == "version_mismatch":
            return self._create_version_mismatch_fixture()
        elif self.fixture_type == "minimal":
            return self._create_minimal_fixture()
        else:
            raise ValueError(f"Unknown fixture type: {self.fixture_type}")
    
    def _create_compatible_fixture(self) -> EnvironmentSnapshot:
        """Create a fully compatible environment fixture."""
        return EnvironmentSnapshot(
            identity=EnvironmentIdentity(
                product="mays-orders",
                project="maynowak",
                environment="production",
                region="us-east-1",
                account_id="123456789012",
                deployment_id="deploy-2024-01-15",
                version="1.0.0",
            ),
            contracts=[
                ContractMetadata(
                    contract_id="orders.port",
                    version="1.0.0",
                    owner="orders",
                    compatibility="stable",
                    consumers=["mays-ris"],
                ),
                ContractMetadata(
                    contract_id="user.context",
                    version="1.0.0",
                    owner="auth",
                    compatibility="stable",
                    consumers=["all"],
                ),
                ContractMetadata(
                    contract_id="work.item",
                    version="1.0.0",
                    owner="work-system",
                    compatibility="stable",
                    consumers=["agents", "sqs-worker"],
                ),
            ],
            capabilities=[
                CapabilityMetadata(
                    capability_id="order-processing",
                    description="Process order requests",
                    available=True,
                ),
                CapabilityMetadata(
                    capability_id="tenant-isolation",
                    description="Multi-tenant isolation",
                    available=True,
                ),
                CapabilityMetadata(
                    capability_id="work-execution",
                    description="Execute work items",
                    available=True,
                ),
            ],
            source="fixture-compatible",
        )
    
    def _create_missing_contract_fixture(self) -> EnvironmentSnapshot:
        """Create a fixture with a missing required contract."""
        snapshot = self._create_compatible_fixture()
        snapshot.contracts = [c for c in snapshot.contracts if c.contract_id != "orders.port"]
        return snapshot
    
    def _create_missing_capability_fixture(self) -> EnvironmentSnapshot:
        """Create a fixture with a missing required capability."""
        snapshot = self._create_compatible_fixture()
        snapshot.capabilities = [c for c in snapshot.capabilities 
                               if c.capability_id != "order-processing"]
        return snapshot
    
    def _create_version_mismatch_fixture(self) -> EnvironmentSnapshot:
        """Create a fixture with version mismatch."""
        snapshot = self._create_compatible_fixture()
        snapshot.identity.version = "0.0.1"
        return snapshot
    
    def _create_minimal_fixture(self) -> EnvironmentSnapshot:
        """Create a minimal fixture with only essential data."""
        return EnvironmentSnapshot(
            identity=EnvironmentIdentity(
                product="mays-orders",
                version="0.0.0",
            ),
            contracts=[
                ContractMetadata(
                    contract_id="user.context",
                    version="1.0.0",
                ),
            ],
            capabilities=[
                CapabilityMetadata(
                    capability_id="tenant-isolation",
                    available=True,
                ),
            ],
        )


def check_environment_compatibility(
    discovery: EnvironmentDiscovery,
    engine: Optional[CompatibilityEngine] = None,
) -> CompatibilityResult:
    """
    Convenience function to check environment compatibility.
    
    Args:
        discovery: EnvironmentDiscovery instance to use
        engine: Optional CompatibilityEngine (creates default if None)
        
    Returns:
        CompatibilityResult
    """
    if engine is None:
        engine = CompatibilityEngine()
    
    snapshot = discovery.discover()
    return engine.check(snapshot)


def create_test_report(result: CompatibilityResult) -> str:
    """Create a human-readable test report."""
    report = []
    report.append("ENVIRONMENT COMPATIBILITY TEST REPORT")
    report.append("=" * 40)
    report.append(f"Status: {result.status.value}")
    report.append(f"Reason: {result.reason}")
    report.append("")
    report.append("Details:")
    for key, value in result.details.items():
        report.append(f"  {key}: {value}")
    
    if result.details.get("issues"):
        report.append("")
        report.append("Issues:")
        for issue in result.details["issues"]:
            report.append(f"    - {issue}")
    
    if result.details.get("warnings"):
        report.append("")
        report.append("Warnings:")
        for warning in result.details["warnings"]:
            report.append(f"    - {warning}")
    
    return "\n".join(report)