"""
Example: Simple calculator tool.

Shows a basic tool with multiple operations.
"""

from langchain_core.tools import tool


def create_tools(agent_id: int) -> list:  # noqa: ARG001
    """Create calculator tools."""

    @tool("calculate", description="Perform basic arithmetic operations (add, subtract, multiply, divide)")
    def calculate(operation: str, a: float, b: float) -> dict:
        """Perform arithmetic calculations.

        Args:
            operation: One of 'add', 'subtract', 'multiply', 'divide'
            a: First number
            b: Second number

        Returns:
            Dictionary with success status and result
        """
        operations = {
            "add": a + b,
            "subtract": a - b,
            "multiply": a * b,
            "divide": a / b if b != 0 else None,
        }

        if operation not in operations:
            return {"success": False, "error": f"Unknown operation: {operation}"}

        result = operations[operation]
        if result is None:
            return {"success": False, "error": "Division by zero"}

        return {"success": True, "result": result}

    return [calculate]
