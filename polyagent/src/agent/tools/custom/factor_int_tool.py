from math import isqrt
from langchain_core.tools import tool

def create_tools(agent_id: int) -> list:
    @tool("factor_int", description="Prime-factorize a positive integer. Returns sorted prime factors.")
    def factor_int(n: int) -> dict:
        if not isinstance(n, int) or n < 2:
            return {"success": False, "error": "n must be an integer >= 2"}
        factors = []
        # Factor out 2s
        while n % 2 == 0:
            factors.append(2)
            n //= 2
        # Factor out 3s
        while n % 3 == 0:
            factors.append(3)
            n //= 3
        # Trial division using 6k ± 1 optimization
        f = 5
        while f * f <= n:
            while n % f == 0:
                factors.append(f)
                n //= f
            g = f + 2  # 6k+1, 6k-1 pattern
            while n % g == 0:
                factors.append(g)
                n //= g
            f += 6
        if n > 1:
            factors.append(n)
        factors.sort()
        return {"success": True, "factors": factors}

    return [factor_int]
