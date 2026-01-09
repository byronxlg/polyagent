"""MCP server for principal management tools."""

from fastmcp import FastMCP

from src.models import Principal
from src.services.principal_service import PrincipalService

mcp = FastMCP("principal")


def _serialize_principal(principal: Principal) -> dict:
    """Serialize a Principal to a dict."""
    return {
        "id": str(principal.id),
        "username": principal.username,
        "principal_type": principal.principal_type,
        "created_at": principal.created_at.isoformat(),
    }


@mcp.tool()
def get_principals(principal_id: str, principal_type: str | None = None) -> dict:
    """Get a list of all principals in the system. Optionally filter by type.

    Args:
        principal_id: Your principal ID (injected by agent)
        principal_type: Optional filter - 'ai_agent', 'human', or 'system'
    """
    service = PrincipalService()
    principals = service.get_principals(principal_type=principal_type)
    return {
        "success": True,
        "count": len(principals),
        "principals": [_serialize_principal(p) for p in principals],
    }


@mcp.tool()
def get_principal(principal_id: str, target_principal_id: str) -> dict:
    """Get details about a specific principal by ID.

    Args:
        principal_id: Your principal ID (injected by agent)
        target_principal_id: The ID of the principal to get details for
    """
    service = PrincipalService()
    principal = service.get_principal(target_principal_id)
    if not principal:
        return {"success": False, "error": f"Principal {target_principal_id} not found"}
    return {
        "success": True,
        "principal": _serialize_principal(principal),
    }


if __name__ == "__main__":
    mcp.run(show_banner=False)
