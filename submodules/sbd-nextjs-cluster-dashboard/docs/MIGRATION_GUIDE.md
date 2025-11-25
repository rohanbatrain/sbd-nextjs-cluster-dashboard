# Database Migration Guide

## Overview

The Second Brain Database migration system allows you to export data from one running instance and import it into another. This is useful for:

- Moving data between environments (development → staging → production)
- Creating backups before major changes
- Migrating to a new server
- Sharing data between team members
- Disaster recovery

## Prerequisites

### Requirements

- **Owner Role**: Migration operations require tenant owner role
- **Same SBD Version**: Both instances should run the same version
- **API Token**: Owner-level API token for authentication
- **Network Access**: Ability to connect to both instances
- **Disk Space**: Sufficient space for migration packages

### Security Considerations

✅ **What IS Exported:**
- User accounts (with hashed passwords)
- All collections and documents
- Family relationships and data
- Chat sessions and messages
- IPAM data
- Blog, club, and MemEx data
- Index definitions

❌ **What is NOT Exported:**
- API tokens (security risk)
- Active sessions
- Temporary data
- Migration history itself

## Quick Start

### 1. Export from Source Instance

```bash
python -m second_brain_database.cli.migration_cli export \
  --url http://source-instance:8000 \
  --token <owner_api_token> \
  --output /path/to/export.json.gz \
  --description "Production backup 2025-11-23"
```

### 2. Validate Export Package

```bash
python -m second_brain_database.cli.migration_cli validate \
  --input /path/to/export.json.gz
```

### 3. Import to Target Instance

```bash
python -m second_brain_database.cli.migration_cli import \
  --url http://target-instance:8000 \
  --token <owner_api_token> \
  --input /path/to/export.json.gz \
  --conflict-resolution overwrite
```

## CLI Reference

### Export Command

Export database collections to a migration package.

```bash
python -m second_brain_database.cli.migration_cli export \
  --url <api_url> \
  --token <api_token> \
  --output <output_path> \
  [--collections <collection1> <collection2> ...] \
  [--description <description>]
```

**Options:**
- `--url`: Base URL of the SBD API (default: http://localhost:8000)
- `--token`: API token with owner role (required)
- `--output`: Path to save migration package (required)
- `--collections`: Specific collections to export (optional, default: all)
- `--description`: Optional description for the export

**Example:**
```bash
# Export all collections
python -m second_brain_database.cli.migration_cli export \
  --url http://localhost:8000 \
  --token sbd_token_abc123 \
  --output /backups/full_export_2025-11-23.json.gz

# Export specific collections
python -m second_brain_database.cli.migration_cli export \
  --url http://localhost:8000 \
  --token sbd_token_abc123 \
  --output /backups/users_only.json.gz \
  --collections users permanent_tokens \
  --description "User data backup"
```

### Import Command

Import a migration package into the database.

```bash
python -m second_brain_database.cli.migration_cli import \
  --url <api_url> \
  --token <api_token> \
  --input <input_path> \
  [--collections <collection1> <collection2> ...] \
  [--conflict-resolution <skip|overwrite|fail>] \
  [--no-rollback]
```

**Options:**
- `--url`: Base URL of the SBD API (default: http://localhost:8000)
- `--token`: API token with owner role (required)
- `--input`: Path to migration package (required)
- `--collections`: Specific collections to import (optional, default: all)
- `--conflict-resolution`: How to handle existing data (default: fail)
  - `skip`: Skip existing documents
  - `overwrite`: Replace existing data
  - `fail`: Abort if data exists
- `--no-rollback`: Skip creating rollback point (not recommended)

**Example:**
```bash
# Import with rollback protection
python -m second_brain_database.cli.migration_cli import \
  --url http://localhost:8000 \
  --token sbd_token_abc123 \
  --input /backups/full_export_2025-11-23.json.gz \
  --conflict-resolution overwrite

# Import specific collections without rollback
python -m second_brain_database.cli.migration_cli import \
  --url http://localhost:8000 \
  --token sbd_token_abc123 \
  --input /backups/users_only.json.gz \
  --collections users \
  --conflict-resolution skip \
  --no-rollback
```

### Validate Command

Validate a migration package before importing.

```bash
python -m second_brain_database.cli.migration_cli validate \
  --input <input_path>
```

**Example:**
```bash
python -m second_brain_database.cli.migration_cli validate \
  --input /backups/full_export_2025-11-23.json.gz
```

### List Collections Command

List all available collections that can be migrated.

```bash
python -m second_brain_database.cli.migration_cli list-collections \
  --url <api_url> \
  --token <api_token>
```

**Example:**
```bash
python -m second_brain_database.cli.migration_cli list-collections \
  --url http://localhost:8000 \
  --token sbd_token_abc123
```

## API Reference

All migration endpoints require owner role authorization.

### Export Endpoints

#### POST /api/migration/export

Initiate a database export.

**Request:**
```json
{
  "collections": ["users", "families"],  // optional
  "include_indexes": true,
  "compression": "gzip",
  "description": "Production backup"
}
```

**Response:**
```json
{
  "migration_id": "uuid",
  "status": "completed",
  "migration_type": "export",
  "created_at": "2025-11-23T19:37:09Z",
  "created_by": "user_id",
  "download_url": "/api/migration/export/uuid/download"
}
```

#### GET /api/migration/export/{migration_id}/download

Download an export package.

**Response:** Binary file (application/gzip)

### Import Endpoints

#### POST /api/migration/import

Initiate a database import.

**Request:**
```json
{
  "migration_package_id": "uuid",
  "collections": ["users"],  // optional
  "conflict_resolution": "overwrite",
  "create_rollback": true,
  "validate_only": false
}
```

**Response:**
```json
{
  "migration_id": "uuid",
  "status": "completed",
  "migration_type": "import",
  "rollback_available": true
}
```

#### POST /api/migration/import/validate

Validate a migration package.

**Request:**
```json
{
  "migration_package_id": "uuid"
}
```

**Response:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": ["Version mismatch"],
  "metadata": {...},
  "schema_compatible": true,
  "checksum_valid": true
}
```

#### POST /api/migration/import/{migration_id}/rollback

Rollback a migration.

**Request:**
```json
{
  "migration_id": "uuid",
  "confirm": true
}
```

### Management Endpoints

#### GET /api/migration/history

Get migration history.

**Query Parameters:**
- `limit`: Maximum results (default: 50)
- `offset`: Skip results (default: 0)

**Response:**
```json
{
  "migrations": [...],
  "total_count": 10
}
```

#### GET /api/migration/{migration_id}/status

Get migration status.

**Response:**
```json
{
  "migration_id": "uuid",
  "status": "in_progress",
  "migration_type": "export",
  "progress": {
    "progress_percentage": 45.0,
    "current_collection": "chat_messages",
    "collections_completed": 9,
    "total_collections": 20
  }
}
```

#### DELETE /api/migration/{migration_id}

Delete a migration record.

#### GET /api/migration/collections

List available collections.

## Migration Workflow

### Standard Migration Process

1. **Pre-Migration**
   ```bash
   # Verify owner role access
   # Check disk space
   # Backup target instance (if has data)
   # Test with sample data first
   ```

2. **Export Phase**
   ```bash
   # Export from source
   python -m second_brain_database.cli.migration_cli export \
     --url http://source:8000 \
     --token <token> \
     --output /tmp/migration.json.gz
   ```

3. **Validation Phase**
   ```bash
   # Validate package
   python -m second_brain_database.cli.migration_cli validate \
     --input /tmp/migration.json.gz
   ```

4. **Import Phase**
   ```bash
   # Import to target
   python -m second_brain_database.cli.migration_cli import \
     --url http://target:8000 \
     --token <token> \
     --input /tmp/migration.json.gz \
     --conflict-resolution overwrite
   ```

5. **Post-Migration**
   ```bash
   # Verify data integrity
   # Test critical functionality
   # Monitor for issues
   ```

### Rollback Procedure

If import fails or data is incorrect:

```bash
# Using API
curl -X POST http://target:8000/api/migration/import/{migration_id}/rollback \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"migration_id": "uuid", "confirm": true}'
```

## Troubleshooting

### Common Issues

#### 1. Permission Denied (403)

**Problem:** User doesn't have owner role

**Solution:**
- Verify you have owner role in tenant
- Check API token is valid
- Ensure token has owner permissions

#### 2. Checksum Mismatch

**Problem:** Migration package corrupted

**Solution:**
- Re-download or re-export package
- Verify file integrity
- Check disk space

#### 3. Version Mismatch

**Problem:** Source and target have different SBD versions

**Solution:**
- Upgrade/downgrade to match versions
- Check compatibility warnings
- Test in staging first

#### 4. Collection Already Has Data

**Problem:** Conflict resolution set to "fail"

**Solution:**
- Use `--conflict-resolution overwrite` or `skip`
- Clear target collections first
- Import to fresh instance

#### 5. Out of Disk Space

**Problem:** Not enough space for migration package

**Solution:**
- Free up disk space
- Use external storage
- Export specific collections only

## Best Practices

### Before Migration

- ✅ Test migration with sample data first
- ✅ Verify both instances are same version
- ✅ Create backup of target instance
- ✅ Estimate migration time and plan downtime
- ✅ Validate migration package before import
- ✅ Ensure sufficient disk space

### During Migration

- ✅ Monitor export/import progress
- ✅ Watch for errors in logs
- ✅ Keep migration package secure
- ✅ Don't interrupt the process
- ✅ Use rollback if issues occur

### After Migration

- ✅ Verify document counts match
- ✅ Test critical functionality
- ✅ Check data relationships
- ✅ Monitor for issues
- ✅ Keep migration package as backup
- ✅ Update DNS/configuration if needed

## Security Best Practices

1. **Protect API Tokens**
   - Never commit tokens to version control
   - Use environment variables
   - Rotate tokens regularly

2. **Secure Migration Packages**
   - Store in secure location
   - Encrypt if contains sensitive data
   - Delete after successful migration

3. **Audit Trail**
   - All migrations are logged
   - Review migration history regularly
   - Monitor for unauthorized migrations

4. **Access Control**
   - Only owner role can migrate
   - Limit owner role assignments
   - Review permissions regularly

## Performance Tips

1. **Large Datasets**
   - Export during off-peak hours
   - Use compression (enabled by default)
   - Consider selective collection export

2. **Network Transfer**
   - Use local network when possible
   - Compress before transfer
   - Verify checksums after transfer

3. **Import Optimization**
   - Import to fresh instance when possible
   - Use `overwrite` for faster imports
   - Monitor system resources

## Support

For issues or questions:

1. Check logs: `/var/log/sbd/migration.log`
2. Review migration history: `GET /api/migration/history`
3. Consult documentation: [GitHub](https://github.com/rohanbatrain/second_brain_database)
4. Contact support with migration ID

## Appendix

### Migration Package Format

```json
{
  "metadata": {
    "version": "1.0.0",
    "sbd_version": "0.1.0",
    "export_timestamp": "2025-11-23T19:37:09Z",
    "source_instance": "instance-1",
    "exported_by": "user_id",
    "collections_count": 25,
    "total_documents": 10000,
    "checksum": "sha256:...",
    "compression": "gzip"
  },
  "collections": [
    {
      "collection_name": "users",
      "documents": [...],
      "indexes": [...],
      "metadata": {
        "name": "users",
        "document_count": 100,
        "size_bytes": 50000,
        "checksum": "sha256:..."
      }
    }
  ]
}
```

### Collection Dependencies

Some collections have dependencies and should be imported in order:

1. `users` - Core user data
2. `tenants`, `tenant_memberships` - Multi-tenancy
3. `families`, `family_relationships` - Family data
4. `workspaces` - Workspace data
5. All other collections

The migration system handles this automatically.
