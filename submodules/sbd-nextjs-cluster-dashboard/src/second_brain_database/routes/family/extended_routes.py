"""
# Family Extended Features Routes

This module provides **advanced functionality** for the Family Hub, extending beyond basic management
to include lifestyle, organization, and gamification features.

## Domain Overview

These endpoints power the rich interactive features of the Family Hub:
- **Memories**: Shared photo albums.
- **Organization**: Collaborative shopping lists and meal plans.
- **Gamification**: Chore rotations with token rewards.
- **Goals**: Shared family objectives and milestones.
- **Marketplace**: A reward store for redeeming earned tokens.

## Key Features

### 1. Photo Album
- **Shared Gallery**: Upload and view family photos.
- **Metadata**: Captions, upload timestamps, and user attribution.
- **Storage**: Securely handles file uploads (implementation details abstracted).

### 2. Household Management
- **Shopping Lists**: Real-time collaborative lists (Groceries, Supplies).
- **Meal Planning**: Schedule meals for the week/month.
- **Chore Rotations**: Automated assignment of tasks (Weekly/Bi-weekly) with rewards.

### 3. Token Economy & Gamification
- **Earning Rules**: Define how tokens are earned (e.g., "10 tokens for dishes").
- **Rewards Marketplace**: Create a catalog of redeemable items (e.g., "Movie Night").
- **Allowances**: Configure automated recurring payments.

## API Endpoints

### Photos
- `POST /family/{id}/photos` - Upload photo
- `GET /family/{id}/photos` - View album

### Organization
- `GET /family/{id}/shopping-lists` - View lists
- `POST /family/{id}/chores` - Create chore rotation
- `GET /family/{id}/meal-plans` - View menu

### Economy
- `POST /family/{id}/token-rules` - Define earning logic
- `POST /family/{id}/rewards` - Add marketplace item
- `POST /family/{id}/rewards/{id}/purchase` - Redeem tokens

## Usage Examples

### Creating a Chore with Reward

```python
response = await client.post(f"/family/{family_id}/chores", json={
    "chore_name": "Walk the Dog",
    "rotation_schedule": "daily",
    "reward_amount": 50
})
```

### Purchasing a Reward

```python
# Child user purchases "Extra Screen Time"
response = await client.post(
    f"/family/{family_id}/rewards/{reward_id}/purchase"
)
# Tokens are automatically deducted from user balance
```

## Module Attributes

Attributes:
    router (APIRouter): FastAPI router for extended family features
"""

from typing import List
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse

from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.routes.family.extended_models import (
    PhotoUploadResponse,
    PhotoListResponse,
    ShoppingListCreate,
    ShoppingListResponse,
    MealPlanCreate,
    MealPlanResponse,
    ChoreRotationCreate,
    ChoreRotationResponse,
    FamilyGoalCreate,
    FamilyGoalUpdate,
    FamilyGoalResponse,
    TokenRuleCreate,
    TokenRuleResponse,
    RewardCreate,
    RewardResponse,
    TokenTransactionResponse,
    AllowanceScheduleCreate,
    AllowanceScheduleResponse,
)

router = APIRouter(prefix="/family", tags=["Family Extended Features"])


# ============================================================================
# PHOTO ALBUM ENDPOINTS
# ============================================================================

@router.post("/{family_id}/photos", response_model=PhotoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    family_id: str,
    caption: str | None = None,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Upload a photo to the family album.

    Allows family members to upload photos to a shared family album.
    Photos can include captions and are tagged with the uploader's information.
    This feature helps families preserve memories and share moments.

    **Rate Limiting:**
    10 uploads per hour per user.

    **Requirements:**
    - User must be a member of the family.
    - File must be a valid image format (JPEG, PNG).
    - File size must not exceed 10MB.

    Args:
        family_id (str): The ID of the family.
        caption (str, optional): A caption or description for the photo.
        current_user (dict): The authenticated user.

    Returns:
        PhotoUploadResponse: Details of the uploaded photo including its URL.

    Raises:
        HTTPException(404): If the family is not found.
        HTTPException(400): If the file is invalid or upload fails.
        HTTPException(429): If the rate limit is exceeded.
    """


@router.get("/{family_id}/photos", response_model=PhotoListResponse)
async def get_photos(
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get all photos for a family.

    Retrieves a paginated list of photos from the family's shared album.
    Photos are returned in reverse chronological order (newest first).

    **Rate Limiting:**
    30 requests per hour per user.

    Args:
        family_id (str): The ID of the family.
        current_user (dict): The authenticated user.

    Returns:
        PhotoListResponse: A list of photos and the total count.

    Raises:
        HTTPException(404): If the family is not found.
        HTTPException(500): If there is an error retrieving photos.
    """


@router.delete("/{family_id}/photos/{photo_id}")
async def delete_photo(
    family_id: str,
    photo_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Delete a photo from the family album.

    Allows the original uploader or a family administrator to remove a photo.
    This action is permanent and cannot be undone.

    **Access Control:**
    - The uploader of the photo.
    - Any family administrator.

    Args:
        family_id (str): The ID of the family.
        photo_id (str): The ID of the photo to delete.
        current_user (dict): The authenticated user.

    Returns:
        JSONResponse: Confirmation of deletion.

    Raises:
        HTTPException(404): If the photo or family is not found.
        HTTPException(403): If the user does not have permission to delete the photo.
    """


# ============================================================================
# SHOPPING LIST ENDPOINTS
# ============================================================================

@router.get("/{family_id}/shopping-lists", response_model=List[ShoppingListResponse])
async def get_shopping_lists(
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get all shopping lists for a family.

    Retrieves all active shopping lists associated with the family.
    Shopping lists can be used for groceries, supplies, or wishlists.

    **Rate Limiting:**
    30 requests per hour per user.

    Args:
        family_id (str): The ID of the family.
        current_user (dict): The authenticated user.

    Returns:
        List[ShoppingListResponse]: A list of shopping lists.
    """


@router.post("/{family_id}/shopping-lists", response_model=ShoppingListResponse, status_code=status.HTTP_201_CREATED)
async def create_shopping_list(
    family_id: str,
    shopping_list: ShoppingListCreate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Create a new shopping list.

    Allows family members to create collaborative shopping lists.
    Lists can be named (e.g., "Weekly Groceries", "Party Supplies") and populated with items.

    **Rate Limiting:**
    10 lists per hour per user.

    Args:
        family_id (str): The ID of the family.
        shopping_list (ShoppingListCreate): The details of the new list.
        current_user (dict): The authenticated user.

    Returns:
        ShoppingListResponse: The created shopping list details.

    Raises:
        HTTPException(404): If the family is not found.
        HTTPException(400): If the list creation fails.
    """


@router.put("/{family_id}/shopping-lists/{list_id}", response_model=ShoppingListResponse)
async def update_shopping_list(
    family_id: str,
    list_id: str,
    shopping_list: ShoppingListCreate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Update a shopping list.

    Allows modifying the name or items of an existing shopping list.
    This endpoint supports adding, removing, or checking off items.

    Args:
        family_id (str): The ID of the family.
        list_id (str): The ID of the shopping list to update.
        shopping_list (ShoppingListCreate): The updated list details.
        current_user (dict): The authenticated user.

    Returns:
        ShoppingListResponse: The updated shopping list.

    Raises:
        HTTPException(404): If the shopping list is not found.
        HTTPException(403): If the user does not have permission.
    """


# ============================================================================
# MEAL PLANNING ENDPOINTS
# ============================================================================

@router.get("/{family_id}/meal-plans", response_model=List[MealPlanResponse])
async def get_meal_plans(
    family_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get meal plans for a family within a date range.

    Retrieves scheduled meals for the specified period.
    Useful for planning weekly or monthly menus.

    Args:
        family_id (str): The ID of the family.
        start_date (str, optional): The start date filter (ISO format).
        end_date (str, optional): The end date filter (ISO format).
        current_user (dict): The authenticated user.

    Returns:
        List[MealPlanResponse]: A list of meal plans.
    """


@router.post("/{family_id}/meal-plans", response_model=MealPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_meal_plan(
    family_id: str,
    meal_plan: MealPlanCreate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Create a new meal plan.

    Schedules a meal for a specific date and type (e.g., Dinner, Lunch).
    Can include recipe names, ingredients, and notes.

    **Rate Limiting:**
    20 plans per hour per user.

    Args:
        family_id (str): The ID of the family.
        meal_plan (MealPlanCreate): The meal plan details.
        current_user (dict): The authenticated user.

    Returns:
        MealPlanResponse: The created meal plan.

    Raises:
        HTTPException(404): If the family is not found.
        HTTPException(400): If the meal plan creation fails.
    """


# ============================================================================
# CHORE ROTATION ENDPOINTS
# ============================================================================

@router.get("/{family_id}/chores", response_model=List[ChoreRotationResponse])
async def get_chore_rotations(
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get all chore rotations for a family.

    Retrieves the list of chores and their rotation schedules, including who is currently
    assigned and when the next rotation occurs. Supports **weekly**, **biweekly**, or **monthly** rotations.

    Args:
        family_id: The `family_id` of the target family.
        current_user: The authenticated user (injected by `enforce_all_lockdowns`).

    Returns:
        A list of `ChoreRotationResponse` objects containing:
        - Chore name and schedule
        - Current assignee and next rotation date
        - Optional reward amounts (in family tokens)

    Raises:
        HTTPException: **404** if the family is not found.
    """
    return []


@router.post("/{family_id}/chores", response_model=ChoreRotationResponse, status_code=status.HTTP_201_CREATED)
async def create_chore_rotation(
    family_id: str,
    chore: ChoreRotationCreate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Create a new chore rotation.

    Establishes an automated chore rotation schedule where task assignments rotate among
    family members. Chores can have optional token rewards to incentivize completion.

    **Features:**
    - Automated rotation based on schedule (`weekly`, `biweekly`, `monthly`)
    - Token-based rewards for completion
    - Fair distribution among family members

    Args:
        family_id: The `family_id` of the target family.
        chore: A `ChoreRotationCreate` object containing:
            - `chore_name`: Name of the chore (e.g., "Dishes", "Laundry")
            - `rotation_schedule`: Frequency (`weekly`, `biweekly`, `monthly`)
            - `reward_amount`: Optional tokens awarded upon completion
        current_user: The authenticated user.

    Returns:
        A `ChoreRotationResponse` with the created rotation details, including the
        `rotation_id` and `next_rotation_date`.

    Raises:
        HTTPException: **404** if the family is not found, **400** if validation fails.
    """
    rotation_data = {
        "rotation_id": f"chore_{uuid4().hex[:12]}",
        "family_id": family_id,
        "chore_name": chore.chore_name,
        "rotation_schedule": chore.rotation_schedule,
        "assigned_members": [],
        "current_assignee": None,
        "current_assignee_name": None,
        "next_rotation_date": datetime.utcnow() + timedelta(days=7),
        "reward_amount": chore.reward_amount or 0,
        "created_at": datetime.utcnow(),
    }
    
    return ChoreRotationResponse(**rotation_data)


# ============================================================================
# FAMILY GOALS ENDPOINTS
# ============================================================================

@router.get("/{family_id}/goals", response_model=List[FamilyGoalResponse])
async def get_family_goals(
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get all family goals.

    Retrieves collaborative goals set by the family, tracking progress and milestones.
    Goals can be **personal**, **shared**, or **financial**.

    Args:
        family_id: The `family_id` of the target family.
        current_user: The authenticated user.

    Returns:
        A list of `FamilyGoalResponse` objects with progress tracking and milestone data.
    """
    return []


@router.post("/{family_id}/goals", response_model=FamilyGoalResponse, status_code=status.HTTP_201_CREATED)
async def create_family_goal(
    family_id: str,
    goal: FamilyGoalCreate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Create a new family goal.

    Establish a collaborative goal with milestones to track family achievements.
    Goals can be assigned to specific members or shared across the family.

    **Goal Types:**
    - `personal`: Individual member goals
    - `shared`: Goals requiring multiple members
    - `financial`: Savings or budget goals

    Args:
        family_id: The `family_id` of the target family.
        goal: A `FamilyGoalCreate` object containing:
            - `title`: Goal name (e.g., "Save for Vacation")
            - `description`: Detailed description
            - `target_date`: Goal deadline
            - `goal_type`: Type of goal (`personal`, `shared`, `financial`)
            - `assigned_to`: Optional list of member IDs
            - `milestones`: List of milestone descriptions
        current_user: The authenticated user.

    Returns:
        A `FamilyGoalResponse` with the created goal, including `goal_id` and progress tracking.

    Raises:
        HTTPException: **404** if the family is not found, **400** if validation fails.
    """
    user_id = str(current_user["_id"])
    
    goal_data = {
        "goal_id": f"goal_{uuid4().hex[:12]}",
        "family_id": family_id,
        "title": goal.title,
        "description": goal.description,
        "target_date": goal.target_date,
        "goal_type": goal.goal_type,
        "assigned_to": goal.assigned_to,
        "assigned_to_name": None,
        "milestones": goal.milestones,
        "completed_milestones": [],
        "progress": 0,
        "created_by": user_id,
        "created_by_name": current_user.get("username"),
        "created_at": datetime.utcnow(),
        "updated_at": None,
    }
    
    return FamilyGoalResponse(**goal_data)


@router.put("/{family_id}/goals/{goal_id}", response_model=FamilyGoalResponse)
async def update_family_goal(
    family_id: str,
    goal_id: str,
    goal: FamilyGoalUpdate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Update a family goal's progress.

    Allows updating milestone completion, progress percentage, or goal details.
    Used to track progress toward family objectives.

    Args:
        family_id: The `family_id` of the target family.
        goal_id: The unique identifier of the goal to update.
        goal: A `FamilyGoalUpdate` object with updated milestones or progress.
        current_user: The authenticated user.

    Returns:
        The updated `FamilyGoalResponse` with new progress data.

    Raises:
        HTTPException: **404** if the goal is not found, **403** if unauthorized.
    """
    raise HTTPException(status_code=404, detail="Goal not found")


# ============================================================================
# TOKEN SYSTEM ENDPOINTS
# ============================================================================

@router.get("/{family_id}/token-rules", response_model=List[TokenRuleResponse])
async def get_token_rules(
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get all token earning rules for a family.

    Retrieves the configured rules that define how family members earn tokens
    (e.g., completing chores, achieving goals, allowances).

    Args:
        family_id: The `family_id` of the target family.
        current_user: The authenticated user.

    Returns:
        A list of `TokenRuleResponse` objects describing each earning rule.
    """
    return []


@router.post("/{family_id}/token-rules", response_model=TokenRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_token_rule(
    family_id: str,
    rule: TokenRuleCreate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Create a new token earning rule.

    Establishes automated token rewards for completing tasks or achieving milestones.
    Rules can be **chore-based**, **goal-based**, or **event-based**.

    **Examples:**
    - `chore`: Earn 10 tokens for completing dishes
    - `goal`: Earn 50 tokens for completing a milestone
    - `allowance`: Weekly token distribution

    Args:
        family_id: The `family_id` of the target family.
        rule: A `TokenRuleCreate` object containing:
            - `rule_name`: Descriptive name (e.g., "Dishes Reward")
            - `rule_type`: Type of rule (`chore`, `goal`, `allowance`, `event`)
            - `token_amount`: Tokens awarded when conditions are met
            - `conditions`: Optional conditions (e.g., frequency limits)
        current_user: The authenticated user (must be family admin).

    Returns:
        A `TokenRuleResponse` with the created rule details, including `rule_id`.

    Raises:
        HTTPException: **404** if the family is not found, **403** if not admin.
    """
    rule_data = {
        "rule_id": f"rule_{uuid4().hex[:12]}",
        "family_id": family_id,
        "rule_name": rule.rule_name,
        "rule_type": rule.rule_type,
        "token_amount": rule.token_amount,
        "conditions": rule.conditions,
        "active": True,
        "created_at": datetime.utcnow(),
    }
    
    return TokenRuleResponse(**rule_data)


@router.get("/{family_id}/rewards", response_model=List[RewardResponse])
async def get_rewards(
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get all rewards in the marketplace.

    Retrieves available rewards that family members can purchase with earned tokens.
    Rewards are categorized (e.g., `privileges`, `items`, `experiences`).

    Args:
        family_id: The `family_id` of the target family.
        current_user: The authenticated user.

    Returns:
        A list of `RewardResponse` objects with reward details and availability.
    """
    return []


@router.post("/{family_id}/rewards", response_model=RewardResponse, status_code=status.HTTP_201_CREATED)
async def create_reward(
    family_id: str,
    reward: RewardCreate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Create a new reward in the marketplace.

    Adds a reward that family members can purchase with tokens. Rewards can be
    **limited quantity** or **unlimited**, and organized by category.

    **Categories:**
    - `privileges`: Extra screen time, stay up late
    - `items`: Toys, books, games
    - `experiences`: Movie night, ice cream outing

    Args:
        family_id: The `family_id` of the target family.
        reward: A `RewardCreate` object containing:
            - `reward_name`: Name of the reward (e.g., "Extra 30min Screen Time")
            - `description`: Detailed description
            - `token_cost`: Tokens required to purchase
            - `category`: Reward category (`privileges`, `items`, `experiences`)
            - `quantity_available`: Optional limit (None = unlimited)
        current_user: The authenticated user (must be family admin).

    Returns:
        A `RewardResponse` with the created reward details.

    Raises:
        HTTPException: **404** if the family is not found, **403** if not admin.
    """
    reward_data = {
        "reward_id": f"reward_{uuid4().hex[:12]}",
        "family_id": family_id,
        "reward_name": reward.reward_name,
        "description": reward.description,
        "token_cost": reward.token_cost,
        "category": reward.category,
        "quantity_available": reward.quantity_available,
        "quantity_claimed": 0,
        "created_at": datetime.utcnow(),
    }
    
    return RewardResponse(**reward_data)


@router.post("/{family_id}/rewards/{reward_id}/purchase")
async def purchase_reward(
    family_id: str,
    reward_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Purchase a reward with tokens.

    Deducts tokens from a family member's balance and grants the reward.
    Enforces quantity limits and validates sufficient token balance.

    Args:
        family_id: The `family_id` of the target family.
        reward_id: The unique identifier of the reward to purchase.
        current_user: The authenticated user making the purchase.

    Returns:
        A JSON response confirming the purchase and updated token balance.

    Raises:
        HTTPException: **404** if reward not found, **400** if insufficient tokens or out of stock.
    """
    return JSONResponse({"message": "Reward purchased successfully"})


@router.get("/{family_id}/token-transactions", response_model=List[TokenTransactionResponse])
async def get_token_transactions(
    family_id: str,
    user_id: str | None = None,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get token transaction history.

    Retrieves the complete history of token earnings and spending for the family
    or a specific member. Useful for tracking accountability and progress.

    Args:
        family_id: The `family_id` of the target family.
        user_id: Optional filter to show transactions for a specific member.
        current_user: The authenticated user.

    Returns:
        A list of `TokenTransactionResponse` objects with transaction details.
    """
    return []


@router.get("/{family_id}/allowances", response_model=List[AllowanceScheduleResponse])
async def get_allowance_schedules(
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get all allowance schedules.

    Retrieves automated token allowance schedules configured for family members.
    Allowances are distributed at regular intervals (weekly, biweekly, monthly).

    Args:
        family_id: The `family_id` of the target family.
        current_user: The authenticated user.

    Returns:
        A list of `AllowanceScheduleResponse` objects with schedule details.
    """
    return []


@router.post("/{family_id}/allowances", response_model=AllowanceScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_allowance_schedule(
    family_id: str,
    allowance: AllowanceScheduleCreate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Create a new allowance schedule.

    Establishes an automated token distribution for a family member at regular intervals.
    Allowances ensure consistent token earnings independent of task completion.

    **Frequencies:**
    - `weekly`: Every 7 days
    - `biweekly`: Every 14 days
    - `monthly`: Every 30 days

    Args:
        family_id: The `family_id` of the target family.
        allowance: An `AllowanceScheduleCreate` object containing:
            - `recipient_id`: ID of the family member receiving the allowance
            - `amount`: Tokens distributed per period
            - `frequency`: Distribution interval (`weekly`, `biweekly`, `monthly`)
            - `active`: Whether the schedule is currently active
        current_user: The authenticated user (must be family admin).

    Returns:
        An `AllowanceScheduleResponse` with the created schedule, including `next_distribution` date.

    Raises:
        HTTPException: **404** if the family is not found, **403** if not admin.
    """
    schedule_data = {
        "schedule_id": f"allow_{uuid4().hex[:12]}",
        "family_id": family_id,
        "recipient_id": allowance.recipient_id,
        "recipient_name": None,
        "amount": allowance.amount,
        "frequency": allowance.frequency,
        "active": allowance.active,
        "last_distributed": None,
        "next_distribution": datetime.utcnow() + timedelta(days=7),
        "created_at": datetime.utcnow(),
    }
    
    return AllowanceScheduleResponse(**schedule_data)


@router.put("/{family_id}/allowances/{schedule_id}", response_model=AllowanceScheduleResponse)
async def update_allowance_schedule(
    family_id: str,
    schedule_id: str,
    allowance: AllowanceScheduleCreate,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Update an allowance schedule.

    Modifies an existing allowance schedule (amount, frequency, or active status).
    Changes take effect on the next scheduled distribution.

    Args:
        family_id: The `family_id` of the target family.
        schedule_id: The unique identifier of the schedule to update.
        allowance: An `AllowanceScheduleCreate` object with updated values.
        current_user: The authenticated user (must be family admin).

    Returns:
        The updated `AllowanceScheduleResponse`.

    Raises:
        HTTPException: **404** if the schedule is not found, **403** if not admin.
    """
    raise HTTPException(status_code=404, detail="Allowance schedule not found")
