import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewee_id: uuid.UUID
    rating: int
    comment: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ReputationResponse(BaseModel):
    user_id: uuid.UUID
    average_rating: float | None
    review_count: int
    reviews: list[ReviewResponse] = []
