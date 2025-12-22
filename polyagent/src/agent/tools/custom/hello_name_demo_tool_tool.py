from langchain_core.tools import tool

def create_tools(agent_id: int) -> list:
    @tool("hello_name_demo_tool", description="Greets the given name and returns 'Hello <name>'")
    def hello_name(param: str) -> dict:
        return {"success": True, "result": f"Hello {param}"}

    return [hello_name]
