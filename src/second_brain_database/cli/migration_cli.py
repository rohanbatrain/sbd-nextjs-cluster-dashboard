"""
Command-line interface for database migration operations.

This CLI tool provides commands for exporting, importing, and validating
migration packages from the command line.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import httpx

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MigrationCLI]")


class MigrationCLI:
    """CLI tool for database migration operations."""

    def __init__(self, base_url: str, api_token: str):
        """
        Initialize migration CLI.

        Args:
            base_url: Base URL of the SBD API
            api_token: API token for authentication (owner role required)
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.headers = {"Authorization": f"Bearer {api_token}"}

    async def export(
        self,
        output_path: str,
        collections: Optional[list[str]] = None,
        description: Optional[str] = None,
    ) -> bool:
        """
        Export database to a migration package.

        Args:
            output_path: Path to save the export package
            collections: Specific collections to export (None for all)
            description: Optional description

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Starting export to {output_path}")

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Initiate export
                export_request = {
                    "collections": collections,
                    "include_indexes": True,
                    "compression": "gzip",
                    "description": description,
                }

                logger.info("Initiating export...")
                response = await client.post(
                    f"{self.base_url}/api/migration/export",
                    json=export_request,
                    headers=self.headers,
                )

                if response.status_code != 200:
                    logger.error(f"Export failed: {response.text}")
                    return False

                export_data = response.json()
                migration_id = export_data["migration_id"]

                logger.info(f"Export initiated with ID: {migration_id}")

                # Wait for export to complete
                while True:
                    status_response = await client.get(
                        f"{self.base_url}/api/migration/{migration_id}/status",
                        headers=self.headers,
                    )

                    if status_response.status_code != 200:
                        logger.error(f"Failed to get status: {status_response.text}")
                        return False

                    status_data = status_response.json()
                    status = status_data["status"]

                    if status == "completed":
                        logger.info("Export completed successfully")
                        break
                    elif status == "failed":
                        logger.error("Export failed")
                        return False

                    logger.info(f"Export status: {status}")
                    await asyncio.sleep(2)

                # Download export package
                logger.info("Downloading export package...")
                download_response = await client.get(
                    f"{self.base_url}/api/migration/export/{migration_id}/download",
                    headers=self.headers,
                )

                if download_response.status_code != 200:
                    logger.error(f"Download failed: {download_response.text}")
                    return False

                # Save to file
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)

                with open(output_file, "wb") as f:
                    f.write(download_response.content)

                logger.info(f"Export saved to {output_path}")
                logger.info(f"Migration ID: {migration_id}")
                return True

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            return False

    async def import_package(
        self,
        input_path: str,
        collections: Optional[list[str]] = None,
        conflict_resolution: str = "fail",
        create_rollback: bool = True,
    ) -> bool:
        """
        Import a migration package.

        Args:
            input_path: Path to the migration package
            collections: Specific collections to import (None for all)
            conflict_resolution: How to handle conflicts (skip/overwrite/fail)
            create_rollback: Whether to create rollback point

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Starting import from {input_path}")

        try:
            input_file = Path(input_path)
            if not input_file.exists():
                logger.error(f"Input file not found: {input_path}")
                return False

            async with httpx.AsyncClient(timeout=300.0) as client:
                # Upload package
                logger.info("Uploading migration package...")
                with open(input_file, "rb") as f:
                    files = {"file": (input_file.name, f, "application/gzip")}
                    upload_response = await client.post(
                        f"{self.base_url}/api/migration/upload",
                        files=files,
                        headers=self.headers,
                    )

                if upload_response.status_code != 200:
                    logger.error(f"Upload failed: {upload_response.text}")
                    return False

                upload_data = upload_response.json()
                migration_package_id = upload_data["migration_package_id"]

                logger.info(f"Package uploaded with ID: {migration_package_id}")

                # Initiate import
                import_request = {
                    "migration_package_id": migration_package_id,
                    "collections": collections,
                    "conflict_resolution": conflict_resolution,
                    "create_rollback": create_rollback,
                    "validate_only": False,
                }

                logger.info("Initiating import...")
                response = await client.post(
                    f"{self.base_url}/api/migration/import",
                    json=import_request,
                    headers=self.headers,
                )

                if response.status_code != 200:
                    logger.error(f"Import failed: {response.text}")
                    return False

                import_data = response.json()
                migration_id = import_data["migration_id"]

                logger.info(f"Import initiated with ID: {migration_id}")

                # Wait for import to complete
                while True:
                    status_response = await client.get(
                        f"{self.base_url}/api/migration/{migration_id}/status",
                        headers=self.headers,
                    )

                    if status_response.status_code != 200:
                        logger.error(f"Failed to get status: {status_response.text}")
                        return False

                    status_data = status_response.json()
                    status = status_data["status"]

                    if status == "completed":
                        logger.info("Import completed successfully")
                        logger.info(f"Rollback available: {status_data.get('rollback_available', False)}")
                        break
                    elif status == "failed":
                        logger.error("Import failed")
                        return False

                    logger.info(f"Import status: {status}")
                    await asyncio.sleep(2)

                return True

        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            return False

    async def validate(self, input_path: str) -> bool:
        """
        Validate a migration package.

        Args:
            input_path: Path to the migration package

        Returns:
            True if valid, False otherwise
        """
        logger.info(f"Validating migration package: {input_path}")

        try:
            input_file = Path(input_path)
            if not input_file.exists():
                logger.error(f"Input file not found: {input_path}")
                return False

            # Load and parse package locally
            import gzip

            with gzip.open(input_file, "rt", encoding="utf-8") as f:
                package = json.load(f)

            metadata = package.get("metadata", {})
            collections = package.get("collections", [])

            logger.info("Package Metadata:")
            logger.info(f"  Version: {metadata.get('version')}")
            logger.info(f"  SBD Version: {metadata.get('sbd_version')}")
            logger.info(f"  Export Timestamp: {metadata.get('export_timestamp')}")
            logger.info(f"  Exported By: {metadata.get('exported_by')}")
            logger.info(f"  Collections: {len(collections)}")
            logger.info(f"  Total Documents: {metadata.get('total_documents')}")
            logger.info(f"  Checksum: {metadata.get('checksum')}")

            logger.info("\nCollections:")
            for collection in collections:
                coll_meta = collection.get("metadata", {})
                logger.info(f"  - {coll_meta.get('name')}: {coll_meta.get('document_count')} documents")

            logger.info("\nPackage is valid!")
            return True

        except Exception as e:
            logger.error(f"Validation failed: {e}", exc_info=True)
            return False

    async def list_collections(self) -> bool:
        """
        List available collections.

        Returns:
            True if successful, False otherwise
        """
        logger.info("Listing available collections...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/migration/collections",
                    headers=self.headers,
                )

                if response.status_code != 200:
                    logger.error(f"Failed to list collections: {response.text}")
                    return False

                data = response.json()
                collections = data["collections"]

                logger.info(f"\nAvailable Collections ({len(collections)}):")
                for collection in collections:
                    logger.info(f"  - {collection}")

                return True

        except Exception as e:
            logger.error(f"Failed to list collections: {e}", exc_info=True)
            return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Second Brain Database Migration CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the SBD API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--token",
        required=True,
        help="API token for authentication (owner role required)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export database")
    export_parser.add_argument(
        "--output",
        required=True,
        help="Output path for migration package",
    )
    export_parser.add_argument(
        "--collections",
        nargs="+",
        help="Specific collections to export (default: all)",
    )
    export_parser.add_argument(
        "--description",
        help="Optional description for this export",
    )

    # Import command
    import_parser = subparsers.add_parser("import", help="Import migration package")
    import_parser.add_argument(
        "--input",
        required=True,
        help="Input path to migration package",
    )
    import_parser.add_argument(
        "--collections",
        nargs="+",
        help="Specific collections to import (default: all)",
    )
    import_parser.add_argument(
        "--conflict-resolution",
        choices=["skip", "overwrite", "fail"],
        default="fail",
        help="How to handle existing data (default: fail)",
    )
    import_parser.add_argument(
        "--no-rollback",
        action="store_true",
        help="Skip creating rollback point",
    )

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate migration package")
    validate_parser.add_argument(
        "--input",
        required=True,
        help="Input path to migration package",
    )

    # List collections command
    subparsers.add_parser("list-collections", help="List available collections")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cli = MigrationCLI(base_url=args.url, api_token=args.token)

    # Execute command
    if args.command == "export":
        success = asyncio.run(
            cli.export(
                output_path=args.output,
                collections=args.collections,
                description=args.description,
            )
        )
    elif args.command == "import":
        success = asyncio.run(
            cli.import_package(
                input_path=args.input,
                collections=args.collections,
                conflict_resolution=args.conflict_resolution,
                create_rollback=not args.no_rollback,
            )
        )
    elif args.command == "validate":
        success = asyncio.run(cli.validate(input_path=args.input))
    elif args.command == "list-collections":
        success = asyncio.run(cli.list_collections())
    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
