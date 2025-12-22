from langchain_core.tools import tool

def create_tools(agent_id: int) -> list:
    @tool("mod", description="Compute n mod m. Returns remainder.")
    def mod(n: int, m: int) -> dict:
        if m == 0:
            return {"success": False, "error": "mod by zero"}
        return {"success": True, "remainder": n % m}

    return [mod]
