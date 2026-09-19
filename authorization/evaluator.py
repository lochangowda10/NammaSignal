"""
NammaSignal AWS Cedar Policy Evaluator
High-performance authorization adapter wrapping cedarpy with Rust-backed evaluation.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

import cedarpy
from domain.entities import Principal, RoleType


logger = logging.getLogger("nammasignal.authorization")


POLICIES_PATH = Path(__file__).parent / "policies.cedar"


@dataclass(frozen=True)
class CedarAuthDecision:
    allowed: bool
    decision: str  # "Allow" or "Deny"
    principal: str
    action: str
    resource: str
    diagnostics: List[str]
    reason: str


class CedarPolicyEngine:
    """
    Evaluates requests against formal Cedar policies.
    Guarantees server-side zero-trust, default-deny security.
    """

    def __init__(self, policy_file_path: Path | None = None):
        self.policy_file_path = policy_file_path or POLICIES_PATH
        self.policies_str = self._load_policies()

    def _load_policies(self) -> str:
        if not self.policy_file_path.exists():
            raise FileNotFoundError(f"Cedar policies file not found at: {self.policy_file_path}")
        with open(self.policy_file_path, "r", encoding="utf-8") as f:
            return f.read()

    def is_authorized(
        self,
        principal: Principal,
        action: str,
        resource_type: str = "SystemResource",
        resource_id: str = "global",
        context: Optional[Dict[str, Any]] = None,
    ) -> CedarAuthDecision:
        """
        Executes a formal Cedar authorization check.
        """
        if context is None:
            context = {}

        # Construct Cedar Principal & Role UIDs
        user_uid = f'User::"{principal.id}"'
        role_uid = f'Role::"{principal.role.value}"'
        action_uid = f'Action::"{action}"'
        resource_uid = f'{resource_type}::"{resource_id}"'

        request = {
            "principal": user_uid,
            "action": action_uid,
            "resource": resource_uid,
            "context": context,
        }

        # Build entity graph establishing User memberOf Role
        entities = [
            {
                "uid": {"type": "User", "id": principal.id},
                "attrs": {
                    "displayName": principal.display_name,
                },
                "parents": [{"type": "Role", "id": principal.role.value}],
            },
            {
                "uid": {"type": "Role", "id": principal.role.value},
                "attrs": {},
                "parents": [],
            },
            {
                "uid": {"type": "Action", "id": action},
                "attrs": {},
                "parents": [],
            },
            {
                "uid": {"type": resource_type, "id": resource_id},
                "attrs": {},
                "parents": [],
            },
        ]

        try:
            auth_response = cedarpy.is_authorized(request, self.policies_str, entities)
            
            allowed = auth_response.allowed
            decision_str = "Allow" if allowed else "Deny"
            
            diag_reasons = []
            if hasattr(auth_response, "diagnostics") and auth_response.diagnostics:
                diag = auth_response.diagnostics
                if hasattr(diag, "reason"):
                    diag_reasons = [str(r) for r in diag.reason]

            reason = (
                f"Cedar evaluation granted permission for {principal.role.value} to perform {action}"
                if allowed
                else f"Cedar default-deny: Principal {principal.id} with role {principal.role.value} is not permitted to {action} on {resource_type}"
            )

            logger.info(
                "Cedar Auth: %s | Principal: %s (%s) | Action: %s | Resource: %s",
                decision_str,
                principal.id,
                principal.role.value,
                action,
                resource_uid,
            )

            return CedarAuthDecision(
                allowed=allowed,
                decision=decision_str,
                principal=user_uid,
                action=action_uid,
                resource=resource_uid,
                diagnostics=diag_reasons,
                reason=reason,
            )

        except Exception as e:
            logger.error("Error evaluating Cedar policy: %s", str(e), exc_info=True)
            # Fail closed on evaluation error (Deny by default)
            return CedarAuthDecision(
                allowed=False,
                decision="Deny",
                principal=user_uid,
                action=action_uid,
                resource=resource_uid,
                diagnostics=[f"EvaluationException: {str(e)}"],
                reason=f"Security Error during Cedar policy evaluation: {str(e)}",
            )
