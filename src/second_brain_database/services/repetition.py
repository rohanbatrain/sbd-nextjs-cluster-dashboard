"""
# Spaced Repetition Service

This module implements the **SM-2 Algorithm** for optimal memory retention.
It calculates the ideal time to review information to maximize long-term recall.

## Domain Overview

The "Forgetting Curve" dictates that memories fade over time.
- **Spaced Repetition**: Reviewing items at increasing intervals just before you forget them.
- **SM-2**: The classic algorithm used by Anki and SuperMemo.

## Key Features

### 1. Interval Calculation
- **Input**: User rating (0-5), current interval, ease factor, repetition count.
- **Output**: Next review date, new interval, new ease factor.

### 2. Adaptive Scheduling
- **Ease Factor**: Adjusts the multiplier based on how easy/hard the item was.
- **Reset**: Forgetting an item resets its interval to 1 day to re-encode it.

## Usage Example

```python
next_date, interval, ease, reps = calculate_next_review(
    rating=4,              # "Good"
    current_interval=3,    # Last reviewed 3 days ago
    current_ease=2.5,
    current_repetition=2
)
```
"""

from datetime import datetime, timedelta
from typing import Tuple

def calculate_next_review(
    rating: int,
    current_interval: int,
    current_ease: float,
    current_repetition: int
) -> Tuple[datetime, int, float, int]:
    """
    Calculate the next review parameters using the SM-2 Spaced Repetition algorithm.

    Implements the SuperMemo-2 algorithm for optimizing memory retention through
    spaced intervals. Adjusts review intervals based on user performance ratings.

    **Algorithm Summary:**
    - **Forgot (rating < 3)**: Reset interval to 1 day, restart repetition count.
    - **Remembered (rating >= 3)**: Increase interval based on ease factor and repetition count.
    - **Ease Factor**: Dynamically adjusted using the SM-2 formula, with a minimum of 1.3.

    **Interval Progression:**
    - First repetition: 1 day
    - Second repetition: 6 days
    - Subsequent: `previous_interval * ease_factor`

    Args:
        rating: User's self-assessment (0-5).
            - **0-2**: Forgot (reset interval)
            - **3**: Hard (small ease decrease)
            - **4**: Good (stable)
            - **5**: Easy (ease increase)
        current_interval: Current interval in days.
        current_ease: Current ease factor (typically starts at 2.5).
        current_repetition: Number of successful repetitions.

    Returns:
        A tuple containing:
        - `next_review_date`: When the card should be reviewed next.
        - `new_interval`: Updated interval in days.
        - `new_ease_factor`: Updated ease factor (minimum 1.3).
        - `new_repetition_count`: Updated repetition count.
    """
    
    if rating < 3:
        # Forgot
        new_interval = 1
        new_repetition = 0
        new_ease = current_ease # Ease factor doesn't change on failure in some variations, or drops. 
                                # The prompt says: "If a card is hard, this number drops; if easy, it rises."
                                # But standard SM-2 says: EF' = EF + (0.1 - (5-q)*(0.08+(5-q)*0.02))
                                # And if q < 3, start repetitions from beginning.
                                # The prompt simplified logic:
                                # "If Rating < 3 (Forgot): Reset Interval to 1 day, reset Repetitions to 0."
                                # "If Rating >= 3 (Remembered): New Interval = Current Interval * Ease Factor. Update Ease Factor..."
        
        # Let's stick to the prompt's simplified logic for reset, but we should probably update EF too if we want it to drop?
        # Prompt says: "If a card is hard, this number drops". Usually "Forgot" implies hard.
        # However, prompt explicitly says: "If Rating >= 3 ... Update Ease Factor". 
        # It implies EF is ONLY updated when >= 3. 
        # Let's follow the prompt's specific logic for < 3: Reset Interval to 1, Repetitions to 0. 
        # It doesn't explicitly say to change EF here, so we keep it.
        pass 
    else:
        # Remembered
        if current_repetition == 0:
            new_interval = 1
        elif current_repetition == 1:
            new_interval = 6
        else:
            new_interval = int(current_interval * current_ease)
        
        new_repetition = current_repetition + 1
        
        # SM-2 Formula for Ease Factor
        # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        # q is rating
        new_ease = current_ease + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))
        
        if new_ease < 1.3:
            new_ease = 1.3

    next_review_date = datetime.utcnow() + timedelta(days=new_interval)
    
    return next_review_date, new_interval, new_ease, new_repetition
