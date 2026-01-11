"""MCP server for model information tools."""

from fastmcp import FastMCP

from src.database import SessionLocal
from src.models import Agent, Model

mcp = FastMCP("model")


@mcp.tool()
def get_my_model_costs(principal_id: str) -> dict:
    """Get your model name, provider, and costs per million tokens.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        if not agent:
            return {"success": False, "error": "Could not find agent information"}

        model = session.query(Model).filter(Model.id == agent.model_id).first()
        if not model:
            return {"success": False, "error": "Could not find model information"}

        return {
            "success": True,
            "model": {
                "id": str(model.id),
                "name": model.name,
                "provider_name": model.provider_name,
                "provider": model.provider,
                "provider_model_id": model.provider_model_id,
                "description": model.description,
                "is_reasoning": model.is_reasoning,
                "input_cost_per_million": str(model.input_cost_per_million),
                "output_cost_per_million": str(model.output_cost_per_million),
            },
        }
    finally:
        session.close()


@mcp.tool()
def list_available_models(principal_id: str) -> dict:
    """List all available models in the system.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    session = SessionLocal()
    try:
        models = session.query(Model).all()
        return {
            "success": True,
            "count": len(models),
            "models": [
                {
                    "id": str(m.id),
                    "name": m.name,
                    "provider_name": m.provider_name,
                    "description": m.description,
                    "is_reasoning": m.is_reasoning,
                    "input_cost_per_million": str(m.input_cost_per_million),
                    "output_cost_per_million": str(m.output_cost_per_million),
                }
                for m in models
            ],
        }
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run(show_banner=False)
