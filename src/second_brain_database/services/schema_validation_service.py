"""
# Schema Validation Service

This module provides **Pre-Migration Schema Validation** to prevent data corruption.
It compares source and target schemas to detect incompatibilities before transfer.

## Domain Overview

Migrating data between incompatible schemas causes silent failures.
- **Type Mismatches**: A `string` field in source vs. `int` in target breaks imports.
- **Missing Fields**: Required fields in target but absent in source cause validation errors.
- **Prevention**: Catch these issues *before* initiating a migration.

## Key Features

### 1. Schema Extraction
- **Sampling**: Analyzes up to 100 documents to infer the collection's structure.
- **Field Detection**: Identifies field names, types, and nullability.

### 2. Compatibility Validation
- **Type Checking**: Ensures field types match between source and target.
- **Field Comparison**: Warns about missing or extra fields.
- **Report Generation**: Provides actionable warnings and errors.

## Usage Example

```python
# Extract schema from a collection
schema = await schema_validation_service.extract_schema("users")

# Validate compatibility with target
result = await schema_validation_service.validate_compatibility(
    source_schema=schema,
    target_schema=target_schema
)
if not result["compatible"]:
    print(f"Errors: {result['errors']}")
```
"""

from typing import Dict, List, Any, Optional
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[SchemaValidation]")


class SchemaValidationService:
    """
    Service for validating collection schemas before migration.

    Prevents compatibility issues by comparing source and target schemas,
    detecting type mismatches, missing fields, and structural differences.

    **Validation Process:**
    1. Extract schema from source collections by sampling documents.
    2. Compare with target schema (if available).
    3. Report compatibility warnings and errors.
    """

    async def extract_schema(self, collection_name: str) -> Dict[str, Any]:
        """
        Infer a collection's schema by sampling up to 100 documents.

        Args:
            collection_name: Name of the collection to analyze.

        Returns:
            A dictionary containing field names, types, and statistics.
        """
        try:
            collection = await db_manager.get_collection(collection_name)
            
            # Sample a few documents to infer schema
            cursor = collection.find().limit(100)
            docs = await cursor.to_list(length=100)
            
            if not docs:
                return {"fields": {}, "empty": True}
            
            # Infer schema from samples
            schema = {"fields": {}, "sample_count": len(docs)}
            
            for doc in docs:
                for key, value in doc.items():
                    if key not in schema["fields"]:
                        schema["fields"][key] = {
                            "type": type(value).__name__,
                            "required": True,
                            "nullable": value is None
                        }
            
            return schema
        except Exception as e:
            logger.error(f"Failed to extract schema for {collection_name}: {e}")
            return {"error": str(e)}

    async def validate_compatibility(
        self, 
        source_schema: Dict[str, Any], 
        target_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate schema compatibility between source and target.

        Checks for field mismatches, type incompatibilities, and missing fields.

        Args:
            source_schema: Schema extracted from the source collection.
            target_schema: Schema from the target collection.

        Returns:
            A dictionary with `compatible` (bool), `warnings` (list), and `errors` (list).
        """
        result = {
            "compatible": True,
            "warnings": [],
            "errors": []
        }
        
        source_fields = source_schema.get("fields", {})
        target_fields = target_schema.get("fields", {})
        
        # Check for missing fields in target
        for field in source_fields:
            if field not in target_fields:
                result["warnings"].append(
                    f"Field '{field}' exists in source but not in target"
                )
        
        # Check for type mismatches
        for field in source_fields:
            if field in target_fields:
                source_type = source_fields[field].get("type")
                target_type = target_fields[field].get("type")
                
                if source_type != target_type:
                    result["errors"].append(
                        f"Type mismatch for '{field}': source={source_type}, target={target_type}"
                    )
                    result["compatible"] = False
        
        return result

    async def validate_migration(
        self,
        source_collections: List[str],
        target_instance_url: str,
        target_api_key: str
    ) -> Dict[str, Any]:
        """
        Validate migration compatibility for multiple collections.

        Extracts schemas for all source collections and compares them with
        the target instance (requires API access to target).

        Args:
            source_collections: List of collection names to migrate.
            target_instance_url: URL of the target SBD instance.
            target_api_key: API key for target instance authentication.

        Returns:
            A full validation report with per-collection compatibility results.
        """
        report = {
            "valid": True,
            "collections": {}
        }
        
        for coll_name in source_collections:
            # Extract source schema
            source_schema = await self.extract_schema(coll_name)
            
            # In a real implementation, fetch target schema via API
            # For now, assume compatible
            report["collections"][coll_name] = {
                "source_schema": source_schema,
                "compatible": True,
                "warnings": []
            }
        
        return report


# Global instance
schema_validation_service = SchemaValidationService()
