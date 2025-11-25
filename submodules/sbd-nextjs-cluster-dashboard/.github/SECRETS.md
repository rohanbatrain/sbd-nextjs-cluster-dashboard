# GitHub Secrets Configuration

This document lists all GitHub secrets required for the CI/CD workflows.

## Required Secrets

### Docker Hub

**`DOCKER_HUB_TOKEN`** (Required)
- **Description**: Docker Hub access token for pushing images
- **How to create**:
  1. Go to https://hub.docker.com/settings/security
  2. Click "New Access Token"
  3. Name it "GitHub Actions"
  4. Copy the token
  5. Add to GitHub: Settings → Secrets and variables → Actions → New repository secret

### GitHub Container Registry

**`GITHUB_TOKEN`** (Automatic)
- **Description**: Automatically provided by GitHub Actions
- **No action required**: This is automatically available in all workflows

## Optional Secrets (Production)

These secrets are only needed if you're deploying to production or running production builds:

**`MONGODB_PASSWORD`**
- Production MongoDB password
- Used in production deployment workflows

**`REDIS_PASSWORD`**
- Production Redis password
- Used in production deployment workflows

**`QDRANT_API_KEY`**
- Production Qdrant API key
- Used in production deployment workflows

**`JWT_SECRET_KEY`**
- Production JWT secret key
- Generate with: `openssl rand -hex 32`

**`ENCRYPTION_KEY`**
- Production encryption key (Fernet)
- Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## How to Add Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Enter the secret name and value
5. Click **Add secret**

## Verifying Secrets

To verify secrets are properly configured:

1. Go to **Actions** tab in your repository
2. Run a workflow manually (workflow_dispatch)
3. Check the workflow logs for any authentication errors

## Security Best Practices

- ✅ Never commit secrets to the repository
- ✅ Rotate secrets regularly (every 90 days recommended)
- ✅ Use different secrets for dev/staging/production
- ✅ Limit secret access to necessary workflows only
- ✅ Monitor secret usage in workflow logs
- ❌ Never print secrets in workflow logs
- ❌ Never use secrets in pull requests from forks

## Troubleshooting

### "Error: Username and password required"
- Check that `DOCKER_HUB_TOKEN` is set correctly
- Verify the token hasn't expired
- Ensure the token has write permissions

### "Error: authentication required"
- For GHCR, ensure `GITHUB_TOKEN` has package write permissions
- Check repository settings → Actions → General → Workflow permissions

### "Error: secret not found"
- Verify secret name matches exactly (case-sensitive)
- Check secret is set at repository level, not organization level
- Ensure you're in the correct repository
