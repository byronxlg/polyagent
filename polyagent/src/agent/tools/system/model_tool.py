from langchain_core.tools import tool

from src.database import SessionLocal
from src.models import Agent as AgentModel
from src.models import Model


def create_tools(principal_id: str) -> list:
    """Create model tools for a principal."""

    @tool("get_my_model_costs", description="Get your model name, provider, and costs per million tokens")
    def get_my_model_costs() -> dict:
        """Retrieve model cost information."""
        session = SessionLocal()
        try:
            agent = session.query(AgentModel).filter(AgentModel.principal_id == principal_id).first()
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

    return [get_my_model_costs]
