from langchain_core.tools import tool

from src.models import Principal
from src.services.principal_service import PrincipalService


def _serialize_principal(principal: Principal) -> dict:
    """Serialize a Principal to a dict."""
    return {
        "id": str(principal.id),
        "username": principal.username,
        "principal_type": principal.principal_type,
        "created_at": principal.created_at.isoformat(),
    }


def create_tools(principal_id: str) -> list:  # noqa: ARG001
    """Create principal tools. principal_id not needed for these read-only tools."""
    service = PrincipalService()

    @tool(
        "get_principals",
        description="Get a list of all principals in the system. Optionally filter by type.",
    )
    def get_principals(principal_type: str | None = None) -> dict:
        """List all principals, optionally filtered by type (ai_agent, human, system)."""
        principals = service.get_principals(principal_type=principal_type)
        return {
            "success": True,
            "count": len(principals),
            "principals": [_serialize_principal(p) for p in principals],
        }

    @tool("get_principal", description="Get details about a specific principal by ID.")
    def get_principal(principal_id: str) -> dict:
        """Get details of a specific principal."""
        principal = service.get_principal(principal_id)
        if not principal:
            return {"success": False, "error": f"Principal {principal_id} not found"}
        return {
            "success": True,
            "principal": _serialize_principal(principal),
        }

    return [get_principals, get_principal]
