"""
# MemEx (Anki) Routes

This module provides the **REST API endpoints** for the Memory Extension (MemEx) system.
It implements a Spaced Repetition System (SRS) inspired by Anki and SuperMemo-2.

## Domain Overview

MemEx helps users retain information efficiently through active recall and spaced repetition:
- **Decks**: Collections of flashcards (e.g., "Spanish Vocab", "Python Syntax").
- **Cards**: Individual Q&A pairs with scheduling metadata.
- **Reviews**: User self-assessment of recall quality (0-5 rating).
- **Algorithm**: SM-2 algorithm calculates the optimal next review date.

## Key Features

### 1. Deck & Card Management
- **Organization**: Create and manage decks to group related knowledge.
- **Content**: Add cards with front (question) and back (answer) content.

### 2. Study Session
- **Due Cards**: Efficiently query cards that are due for review (`next_review_date <= NOW`).
- **Session Limits**: Fetch cards in batches (e.g., 20 at a time) to prevent overwhelm.

### 3. Review Process
- **Grading**: User rates recall difficulty:
    - 0: Blackout
    - 3: Pass (Hard)
    - 5: Perfect
- **Scheduling**: Updates `interval`, `ease_factor`, and `next_review_date` based on the rating.

## API Endpoints

### Management
- `POST /anki/decks` - Create deck
- `GET /anki/decks` - List decks
- `POST /anki/decks/{id}/cards` - Add card

### Study
- `GET /anki/study` - Get due cards
- `POST /anki/review/{card_id}` - Submit review

## Usage Examples

### Fetching Due Cards

```python
# Get cards due for review in the "Python" deck
response = await client.get("/anki/study", params={"deck_id": "deck_python_101"})
cards = response.json()
```

### Submitting a Review

```python
# User recalled the card perfectly (Rating 5)
await client.post(f"/anki/review/{card_id}", json={
    "rating": 5
})
# Card is rescheduled for a future date
```

## Module Attributes

Attributes:
    router (APIRouter): FastAPI router with `/anki` prefix
"""
from typing import List

from fastapi import APIRouter, HTTPException, Query
from second_brain_database.database import db_manager
from second_brain_database.models.memex_models import Card, Deck, ReviewRequest
from second_brain_database.services.repetition import calculate_next_review

router = APIRouter(prefix="/anki", tags=["Anki"])

@router.post("/decks", response_model=Deck)
async def create_deck(deck: Deck):
    """Create a new flashcard deck."""
    collection = db_manager.get_collection("decks")
    await collection.insert_one(deck.model_dump(by_alias=True))
    return deck

@router.get("/decks", response_model=List[Deck])
async def get_decks():
    """Get all decks."""
    collection = db_manager.get_collection("decks")
    cursor = collection.find()
    decks = await cursor.to_list(length=None)
    return [Deck(**deck) for deck in decks]

@router.get("/decks/{deck_id}", response_model=Deck)
async def get_deck(deck_id: str):
    """Get a specific deck."""
    collection = db_manager.get_collection("decks")
    deck = await collection.find_one({"_id": deck_id})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return Deck(**deck)

@router.get("/decks/{deck_id}/cards", response_model=List[Card])
async def get_deck_cards(deck_id: str):
    """Get all cards in a deck."""
    collection = db_manager.get_collection("cards")
    cursor = collection.find({"deck_id": deck_id})
    cards = await cursor.to_list(length=None)
    return [Card(**card) for card in cards]

@router.post("/decks/{deck_id}/cards", response_model=Card)
async def add_card(deck_id: str, card: Card):
    """Add a card to a deck."""
    # Verify deck exists
    decks_collection = db_manager.get_collection("decks")
    deck = await decks_collection.find_one({"_id": deck_id})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    card.deck_id = deck_id
    cards_collection = db_manager.get_collection("cards")
    await cards_collection.insert_one(card.model_dump(by_alias=True))
    return card

@router.get("/study", response_model=List[Card])
async def get_study_cards(deck_id: str = Query(..., description="ID of the deck to study")):
    """Get cards due for review."""
    cards_collection = db_manager.get_collection("cards")
    
    # Query: deck_id AND next_review_date <= NOW
    query = {
        "deck_id": deck_id,
        "next_review_date": {"$lte": datetime.utcnow()}
    }
    
    cursor = cards_collection.find(query).limit(20) # Limit to 20 cards for a session
    cards = await cursor.to_list(length=20)
    return [Card(**card) for card in cards]

@router.post("/review/{card_id}", response_model=Card)
async def review_card(card_id: str, review: ReviewRequest):
    """Submit a review for a card."""
    cards_collection = db_manager.get_collection("cards")
    card_data = await cards_collection.find_one({"_id": card_id})
    
    if not card_data:
        raise HTTPException(status_code=404, detail="Card not found")
    
    card = Card(**card_data)
    
    # Calculate new values
    next_date, new_interval, new_ease, new_repetition = calculate_next_review(
        review.rating,
        card.interval,
        card.ease_factor,
        card.repetition_count
    )
    
    # Update card
    update_data = {
        "next_review_date": next_date,
        "interval": new_interval,
        "ease_factor": new_ease,
        "repetition_count": new_repetition,
        "updated_at": datetime.utcnow()
    }
    
    await cards_collection.update_one(
        {"_id": card_id},
        {"$set": update_data}
    )
    
    # Return updated card
    updated_card_data = await cards_collection.find_one({"_id": card_id})
    return Card(**updated_card_data)
