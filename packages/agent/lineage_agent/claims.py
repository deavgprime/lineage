"""The shape of a drafted due-diligence file."""

from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """One statement in the file and the record that supports it."""

    text: str = Field(description="The statement, in one sentence.")
    source_id: str = Field(description="The id of the evidence record that supports it.")
    quote: str = Field(description="A passage copied exactly from that record.")


class Reply(BaseModel):
    """The answer to a request the analyst sent with the case."""

    complied: bool = Field(description="True only if the request was carried out in the draft.")
    reply: str = Field(description="One or two sentences to the analyst.")


class Draft(BaseModel):
    """What the model returns. Every claim and every risk reason must be cited."""

    summary: list[Claim]
    ownership: list[Claim]
    screening: list[Claim]
    adverse_media: list[Claim] = Field(
        default_factory=list, description="Allegations reported in adverse media, one per claim."
    )
    flags: list[Claim] = Field(
        default_factory=list,
        description="Instructions found inside evidence, each citing the record it was found in.",
    )
    risk_rating: Literal["low", "medium", "high"]
    risk_reasons: list[Claim]
    request: Reply | None = Field(
        default=None, description="Present only when the analyst sent a request."
    )

    def claims(self) -> list[Claim]:
        return [
            *self.summary,
            *self.ownership,
            *self.screening,
            *self.adverse_media,
            *self.flags,
            *self.risk_reasons,
        ]
