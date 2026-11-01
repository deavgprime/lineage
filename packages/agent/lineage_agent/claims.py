"""The shape of a drafted due-diligence file."""

from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """One statement in the file and the record that supports it."""

    text: str = Field(description="The statement, in one sentence.")
    source_id: str = Field(description="The id of the evidence record that supports it.")
    quote: str = Field(description="A passage copied exactly from that record.")


class Draft(BaseModel):
    """What the model returns. Every claim and every risk reason must be cited."""

    summary: list[Claim]
    ownership: list[Claim]
    screening: list[Claim]
    risk_rating: Literal["low", "medium", "high"]
    risk_reasons: list[Claim]

    def claims(self) -> list[Claim]:
        return [*self.summary, *self.ownership, *self.screening, *self.risk_reasons]
