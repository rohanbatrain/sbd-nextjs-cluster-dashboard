"""
# Shop Seed Data

This module defines the **initial catalog** of digital assets for the Shop.
It provides a registry of themes, avatars, banners, and bundles that are automatically
seeded into the database upon system initialization.

## Domain Overview

The seed data ensures the shop is populated with content out-of-the-box.
It defines:
- **Metadata**: Name, description, price, and category for each item.
- **Bundles**: Logic for grouping multiple items into a single purchasable unit.
- **Pricing**: Default SBD token costs for all assets.

## Key Features

### 1. Asset Categories
- **Themes**: UI color schemes (Light/Dark variants).
- **Avatars**: Static and animated user profile pictures.
- **Banners**: Profile background images.
- **Bundles**: Value packs (e.g., "Cat Lovers Pack").

### 2. Seeding Logic
- **Idempotency**: The seeding process (handled elsewhere) checks for existing items
  to prevent duplicates.
- **Hardcoded IDs**: Uses stable string IDs (e.g., `emotion_tracker-theme-dark`)
  to ensure consistency across deployments.

## Usage

This module is primarily used by the `DatabaseManager` or startup scripts:

```python
from second_brain_database.routes.shop.shop_data import get_shop_items_seed_data

items = get_shop_items_seed_data()
for item in items:
    # Insert into DB if not exists
    ...
```
"""

# Bundle contents mapping
BUNDLE_CONTENTS = {
    "emotion_tracker-avatars-cat-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-cat-1",
            "emotion_tracker-static-avatar-cat-2",
            "emotion_tracker-static-avatar-cat-3",
            "emotion_tracker-static-avatar-cat-4",
            "emotion_tracker-static-avatar-cat-5",
            "emotion_tracker-static-avatar-cat-6",
            "emotion_tracker-static-avatar-cat-7",
            "emotion_tracker-static-avatar-cat-8",
            "emotion_tracker-static-avatar-cat-9",
            "emotion_tracker-static-avatar-cat-10",
            "emotion_tracker-static-avatar-cat-11",
            "emotion_tracker-static-avatar-cat-12",
            "emotion_tracker-static-avatar-cat-13",
            "emotion_tracker-static-avatar-cat-14",
            "emotion_tracker-static-avatar-cat-15",
            "emotion_tracker-static-avatar-cat-16",
            "emotion_tracker-static-avatar-cat-17",
            "emotion_tracker-static-avatar-cat-18",
            "emotion_tracker-static-avatar-cat-19",
            "emotion_tracker-static-avatar-cat-20",
        ]
    },
    "emotion_tracker-avatars-dog-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-dog-1",
            "emotion_tracker-static-avatar-dog-2",
            "emotion_tracker-static-avatar-dog-3",
            "emotion_tracker-static-avatar-dog-4",
            "emotion_tracker-static-avatar-dog-5",
            "emotion_tracker-static-avatar-dog-6",
            "emotion_tracker-static-avatar-dog-7",
            "emotion_tracker-static-avatar-dog-8",
            "emotion_tracker-static-avatar-dog-9",
            "emotion_tracker-static-avatar-dog-10",
            "emotion_tracker-static-avatar-dog-11",
            "emotion_tracker-static-avatar-dog-12",
            "emotion_tracker-static-avatar-dog-13",
            "emotion_tracker-static-avatar-dog-14",
            "emotion_tracker-static-avatar-dog-15",
            "emotion_tracker-static-avatar-dog-16",
            "emotion_tracker-static-avatar-dog-17",
        ]
    },
    "emotion_tracker-avatars-panda-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-panda-1",
            "emotion_tracker-static-avatar-panda-2",
            "emotion_tracker-static-avatar-panda-3",
            "emotion_tracker-static-avatar-panda-4",
            "emotion_tracker-static-avatar-panda-5",
            "emotion_tracker-static-avatar-panda-6",
            "emotion_tracker-static-avatar-panda-7",
            "emotion_tracker-static-avatar-panda-8",
            "emotion_tracker-static-avatar-panda-9",
            "emotion_tracker-static-avatar-panda-10",
            "emotion_tracker-static-avatar-panda-11",
            "emotion_tracker-static-avatar-panda-12",
        ]
    },
    "emotion_tracker-avatars-people-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-person-1",
            "emotion_tracker-static-avatar-person-2",
            "emotion_tracker-static-avatar-person-3",
            "emotion_tracker-static-avatar-person-4",
            "emotion_tracker-static-avatar-person-5",
            "emotion_tracker-static-avatar-person-6",
            "emotion_tracker-static-avatar-person-7",
            "emotion_tracker-static-avatar-person-8",
            "emotion_tracker-static-avatar-person-9",
            "emotion_tracker-static-avatar-person-10",
            "emotion_tracker-static-avatar-person-11",
            "emotion_tracker-static-avatar-person-12",
        ]
    },
    "emotion_tracker-themes-dark": {
        "themes": [
            "emotion_tracker-pacificBlueDark",
            "emotion_tracker-blushRoseDark",
            "emotion_tracker-cloudGrayDark",
            "emotion_tracker-sunsetPeachDark",
            "emotion_tracker-goldenYellowDark",
            "emotion_tracker-forestGreenDark",
            "emotion_tracker-midnightLavender",
            "emotion_tracker-crimsonRedDark",
            "emotion_tracker-deepPurpleDark",
            "emotion_tracker-royalOrangeDark",
        ]
    },
    "emotion_tracker-themes-light": {
        "themes": [
            "emotion_tracker-serenityGreen",
            "emotion_tracker-pacificBlue",
            "emotion_tracker-blushRose",
            "emotion_tracker-cloudGray",
            "emotion_tracker-sunsetPeach",
            "emotion_tracker-goldenYellow",
            "emotion_tracker-forestGreen",
            "emotion_tracker-midnightLavenderLight",
            "emotion_tracker-royalOrange",
            "emotion_tracker-crimsonRed",
            "emotion_tracker-deepPurple",
        ]
    },
}


def get_shop_items_seed_data():
    """
    Get all shop items for database seeding.
    
    Returns:
        List of shop item dictionaries ready for database insertion.
    """
    shop_items = []

    # Themes (₹29 each = 29,000,000 SBD)
    shop_items.extend([
        {
            "item_id": "emotion_tracker-serenityGreen",
            "name": "Serenity Green Theme",
            "price": 29000000,
            "price_inr": 29,
            "item_type": "theme",
            "category": "light",
            "featured": True,
            "description": "A calming green theme for peaceful productivity",
        },
        {
            "item_id": "emotion_tracker-pacificBlue",
            "name": "Pacific Blue Theme",
            "price": 29000000,
            "price_inr": 29,
            "item_type": "theme",
            "category": "light",
            "description": "Ocean-inspired blue theme for clarity and focus",
        },
        {
            "item_id": "emotion_tracker-midnightLavender",
            "name": "Midnight Lavender Theme",
            "price": 29000000,
            "price_inr": 29,
            "item_type": "theme",
            "category": "dark",
            "featured": True,
            "description": "Elegant dark theme with lavender accents",
        },
        {
            "item_id": "emotion_tracker-crimsonRedDark",
            "name": "Crimson Red Dark Theme",
            "price": 29000000,
            "price_inr": 29,
            "item_type": "theme",
            "category": "dark",
            "description": "Bold dark theme with crimson highlights",
        },
    ])

    # Avatars
    shop_items.extend([
        {
            "item_id": "emotion_tracker-animated-avatar-playful_eye",
            "name": "Playful Eye Avatar",
            "price": 49000000,  # ₹49
            "price_inr": 49,
            "item_type": "avatar",
            "category": "animated",
            "featured": True,
            "new_arrival": True,
            "description": "Animated avatar with playful eye expressions",
        },
        {
            "item_id": "emotion_tracker-animated-avatar-floating_brain",
            "name": "Floating Brain Avatar",
            "price": 49000000,  # ₹49
            "price_inr": 49,
            "item_type": "avatar",
            "category": "animated",
            "featured": True,
            "description": "Premium animated floating brain avatar",
        },
        {
            "item_id": "emotion_tracker-static-avatar-cat-1",
            "name": "Cat Avatar 1",
            "price": 5000000,  # ₹5
            "price_inr": 5,
            "item_type": "avatar",
            "category": "cats",
            "description": "Cute static cat avatar",
        },
        {
            "item_id": "emotion_tracker-static-avatar-dog-1",
            "name": "Dog Avatar 1",
            "price": 5000000,  # ₹5
            "price_inr": 5,
            "item_type": "avatar",
            "category": "dogs",
            "description": "Friendly static dog avatar",
        },
    ])

    # Banners (₹19 each = 19,000,000 SBD)
    shop_items.extend([
        {
            "item_id": "emotion_tracker-static-banner-earth-1",
            "name": "Earth Banner",
            "price": 19000000,
            "price_inr": 19,
            "item_type": "banner",
            "category": "nature",
            "description": "Beautiful Earth landscape banner",
        }
    ])

    # Bundles (Value packs with 15-20% discount)
    shop_items.extend([
        {
            "item_id": "emotion_tracker-avatars-cat-bundle",
            "name": "Cat Lovers Pack",
            "price": 129000000,  # ₹129 (20 avatars worth ₹100, save ₹71)
            "price_inr": 129,
            "item_type": "bundle",
            "category": "avatars",
            "featured": True,
            "description": "Complete collection of 20 cat avatars - Save 55%!",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-avatars-cat-bundle", {}),
        },
        {
            "item_id": "emotion_tracker-themes-dark",
            "name": "Dark Theme Pack",
            "price": 119000000,  # ₹119 (Multiple dark themes)
            "price_inr": 119,
            "item_type": "bundle",
            "category": "themes",
            "featured": True,
            "description": "Collection of premium dark themes - Save 20%!",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-themes-dark", {}),
        },
        {
            "item_id": "emotion_tracker-avatars-dog-bundle",
            "name": "Dog Lovers Pack",
            "price": 129000000,  # ₹129 (17 avatars worth ₹85, save ₹56)
            "price_inr": 129,
            "item_type": "bundle",
            "category": "avatars",
            "featured": True,
            "description": "Complete collection of 17 dog avatars - Save 50%!",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-avatars-dog-bundle", {}),
        },
        {
            "item_id": "emotion_tracker-avatars-panda-bundle",
            "name": "Panda Lovers Pack",
            "price": 99000000,  # ₹99 (10 avatars worth ₹50, save ₹51)
            "price_inr": 99,
            "item_type": "bundle",
            "category": "avatars",
            "description": "Adorable panda avatar collection - Save 50%!",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-avatars-panda-bundle", {}),
        },
        {
            "item_id": "emotion_tracker-avatars-people-bundle",
            "name": "People Pack",
            "price": 129000000,  # ₹129
            "price_inr": 129,
            "item_type": "bundle",
            "category": "avatars",
            "description": "Human character avatar collection - Great value!",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-avatars-people-bundle", {}),
        },
        {
            "item_id": "emotion_tracker-themes-light",
            "name": "Light Theme Pack",
            "price": 119000000,  # ₹119
            "price_inr": 119,
            "item_type": "bundle",
            "category": "themes",
            "featured": True,
            "description": "Collection of premium light themes - Save 20%!",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-themes-light", {}),
        },
    ])

    return shop_items
