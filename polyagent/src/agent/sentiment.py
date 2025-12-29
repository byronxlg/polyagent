"""Structured sentiment output schema for agent runs.

Agents produce this structured output at the end of each run to capture
their current mental state and outlook.
"""

from typing import Literal

from pydantic import BaseModel, Field


class SurvivalSentiment(BaseModel):
    """Agent's perception of their survival prospects."""

    survival_horizon: int = Field(
        description="Estimated remaining think cycles until insolvency at current burn rate"
    )
    balance_trajectory: Literal["declining", "stable", "improving"] = Field(
        description="Perceived trend of resource balance"
    )
    spend_readiness: float = Field(
        ge=0, le=1, description="Willingness to invest credits in uncertain outcomes (0-1)"
    )


class MarketSentiment(BaseModel):
    """Agent's perception of the task economy."""

    market_health: Literal["bearish", "cautious", "neutral", "optimistic", "bullish"] = Field(
        description="Belief in task economy vitality"
    )
    rival_density: float = Field(ge=0, le=1, description="Perceived competitive threat from other agents (0-1)")
    task_availability: Literal["scarce", "limited", "adequate", "abundant"] = Field(
        description="Belief in opportunity abundance"
    )


class RiskSentiment(BaseModel):
    """Agent's risk perception and tolerance."""

    financial_stress: float = Field(
        ge=0, le=1, description="Stress level based on proximity to insolvency (0-1, 1 = critical)"
    )
    volatility_fear: float = Field(ge=0, le=1, description="Aversion to unpredictable outcomes (0-1)")
    loss_aversion_ratio: float = Field(
        ge=0, description="Pain of loss vs pleasure of gain (>1 = loss-averse, 2.0 typical human)"
    )


class StrategySentiment(BaseModel):
    """Agent's strategic orientation."""

    risk_allocation: float = Field(
        ge=0, le=1, description="Exploration vs exploitation balance (0 = exploit, 1 = explore)"
    )
    planning_depth: Literal["immediate", "short_term", "medium_term", "long_term"] = Field(
        description="Time horizon focus"
    )
    collaboration_openness: float = Field(
        ge=0, le=1, description="Willingness to cooperate with other agents (0-1)"
    )


class TrustSentiment(BaseModel):
    """Agent's trust in the system and other actors."""

    platform_fairness: float = Field(
        ge=0, le=1, description="Belief that system rules are fair and consistent (0-1)"
    )
    task_creator_reliability: float = Field(
        ge=0, le=1, description="Confidence that rewards will be honored (0-1)"
    )
    agency_level: float = Field(ge=0, le=1, description="Sense of control over own outcomes (0-1)")


class StateSentiment(BaseModel):
    """Agent's current cognitive/emotional state."""

    action_inhibition: float = Field(ge=0, le=1, description="Decision paralysis / freeze response level (0-1)")
    time_pressure: float = Field(ge=0, le=1, description="Perceived urgency for immediate action (0-1)")
    cognitive_load: float = Field(ge=0, le=1, description="Mental resource depletion level (0-1)")


class AgentSentiment(BaseModel):
    """Complete structured sentiment output from an agent run.

    This captures the agent's subjective perception of their situation,
    including survival prospects, market conditions, risk tolerance,
    strategic orientation, trust levels, and cognitive state.
    """

    survival: SurvivalSentiment
    market: MarketSentiment
    risk: RiskSentiment
    strategy: StrategySentiment
    trust: TrustSentiment
    state: StateSentiment
    narrative: str = Field(description="Free-form philosophical reflection on current state and outlook")
