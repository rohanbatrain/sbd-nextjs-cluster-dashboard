"""
# MemEx (Memory Extension) Models

This module defines the data structures for the **Spaced Repetition System (SRS)**, designed to
optimize long-term memory retention using the **SuperMemo-2 (SM-2)** algorithm. It manages
flashcard decks, individual cards, and the scheduling metadata required for adaptive learning.

## Domain Model Overview

The MemEx system is built on two primary entities:

1.  **Deck**: A container for organizing related flashcards (e.g., "Physics Definitions").
2.  **Card**: A single unit of knowledge with a front (question) and back (answer).

## Key Features

### 1. Adaptive Scheduling
Each card maintains metadata for the SM-2 algorithm:
- **Next Review Date**: When the card should be shown again.
- **Interval**: The gap (in days) between the last review and the next.
- **Ease Factor**: A multiplier reflecting the card's difficulty (starts at 2.5).
- **Repetition Count**: Number of consecutive successful recalls.

### 2. Review Process
Users rate their recall quality on a scale of 0-5:
- **0-2**: Incorrect response (reset interval).
- **3**: Correct but difficult.
- **4**: Correct with hesitation.
- **5**: Perfect recall (increase interval).

## Usage Examples

### Creating a Flashcard

```python
card = Card(
    deck_id="deck_123",
    front_content="What is the speed of light?",
    back_content="299,792,458 m/s"
)
```

### Submitting a Review

```python
# User rated the card as "Easy" (5)
review = ReviewRequest(rating=5)
# The system will now calculate the new interval and ease factor
```

## Module Attributes

Attributes:
    None: This module relies on Pydantic models and does not define global constants.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

class Deck(BaseModel):
    """
    Model representing a collection of flashcards.

    Decks are the top-level organizational unit in MemEx. Users study cards
    grouped by deck (e.g., "Spanish Vocabulary", "Python Standard Library").

    **Fields:**
    *   **id**: Unique UUID for the deck.
    *   **title**: User-facing name of the deck.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id", description="Unique identifier for the deck")
    title: str = Field(..., min_length=1, max_length=200, description="Title of the deck")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of creation")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Physics Definitions",
                "created_at": "2023-01-01T00:00:00Z"
            }
        }

class Card(BaseModel):
    """
    Model representing a single flashcard within a deck.

    Contains the content (front/back) and the scheduling metadata required
    by the SuperMemo-2 (SM-2) algorithm.

    **SM-2 Metadata:**
    *   **interval**: Days until the next review. 0 means due immediately.
    *   **ease_factor**: Multiplier for interval growth. Higher = easier card.
    *   **repetition_count**: Consecutive successful reviews.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id", description="Unique identifier for the card")
    deck_id: str = Field(..., description="ID of the parent deck")
    front_content: str = Field(..., min_length=1, description="Question or prompt shown first")
    back_content: str = Field(..., min_length=1, description="Answer or solution shown after flip")
    
    # Spaced Repetition Metadata
    next_review_date: datetime = Field(default_factory=datetime.utcnow, description="When this card is next due")
    interval: int = Field(default=0, ge=0, description="Interval in days between reviews")
    ease_factor: float = Field(default=2.5, ge=1.3, description="Ease factor multiplier (min 1.3)")
    repetition_count: int = Field(default=0, ge=0, description="Number of consecutive successful recalls")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of creation")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of last update")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "deck_id": "123e4567-e89b-12d3-a456-426614174000",
                "front_content": "What is the speed of light?",
                "back_content": "299,792,458 m/s",
                "next_review_date": "2023-01-01T00:00:00Z",
                "interval": 0,
                "ease_factor": 2.5,
                "repetition_count": 0
            }
        }

class ReviewRequest(BaseModel):
    """
    Request model for submitting a card review.

    The rating determines how the scheduling algorithm updates the card's metadata.

    **Rating Scale:**
    *   **0**: Complete blackout.
    *   **1**: Incorrect response; the correct one remembered.
    *   **2**: Incorrect response; where the correct one seemed easy to recall.
    *   **3**: Correct response recalled with serious difficulty.
    *   **4**: Correct response after a hesitation.
    *   **5**: Perfect recall.
    """

    rating: int = Field(..., ge=0, le=5, description="Quality of recall (0-5)")
