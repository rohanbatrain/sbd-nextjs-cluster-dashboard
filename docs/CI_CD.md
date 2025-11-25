# CI/CD Documentation

This document describes the Continuous Integration and Continuous Deployment (CI/CD) setup for the Second Brain Database project using GitHub Actions.

## Overview

The project uses GitHub Actions workflows to automatically test, build, and deploy Docker images across different environments. All workflows are located in `.github/workflows/`.

## Workflows

### 1. Docker Dev Test (`docker-test-dev.yml`)

**Purpose**: Test Docker setup with development configuration on every PR and push to dev branch.

**Triggers**:
- Pull requests to `dev` or `main` branches
- Pushes to `dev` branch
- Manual dispatch

**What it does**:
1. Validates docker-compose configurations
2. Builds Docker images
3. Starts services (MongoDB, Redis, Qdrant, API)
4. Waits for all services to be healthy
5. Tests API health and docs endpoints
6. Tests database connectivity
7. Shows logs on failure
8. Cleans up resources

**Duration**: ~5-8 minutes

**Status**: ![Docker Dev Test](https://github.com/rohanbatrain/second_brain_database/workflows/Docker%20Dev%20Test/badge.svg)

---

### 2. Docker Test Suite (`docker-test-test.yml`)

**Purpose**: Run comprehensive integration tests with test configuration.

**Triggers**:
- Pull requests to `main` branch
- Pushes to `test` branch
- Manual dispatch

**What it does**:
1. Validates test docker-compose configuration
2. Builds Docker images
3. Starts all services including Celery
4. Installs test dependencies with uv
5. Runs pytest integration tests (`test_docker_services.py`)
6. Generates coverage reports
7. Uploads test results as artifacts
8. Cleans up resources

**Duration**: ~10-15 minutes

**Status**: ![Docker Test Suite](https://github.com/rohanbatrain/second_brain_database/workflows/Docker%20Test%20Suite/badge.svg)

---

### 3. Docker Production Build (`docker-build-prod.yml`)

**Purpose**: Build multi-platform production images with security scanning.

**Triggers**:
- Pushes to `main` branch
- Release tags (`v*`)
- Manual dispatch

**What it does**:
1. Validates production configuration
2. Builds images for linux/amd64 and linux/arm64
3. Runs Trivy security scan
4. Pushes to Docker Hub and GitHub Container Registry
5. Creates multi-platform manifest
6. Uploads security scan results

**Duration**: ~15-20 minutes

**Status**: ![Docker Production Build](https://github.com/rohanbatrain/second_brain_database/workflows/Docker%20Production%20Build/badge.svg)

---

### 4. Build and Push Docker Dev Image (`dev.yml`)

**Purpose**: Build and push development images to registries.

**Triggers**:
- Pushes to `dev` branch

**What it does**:
1. Validates docker-compose dev configuration
2. Builds Docker image
3. Pushes to Docker Hub as `rohanbatra/second_brain_database:dev`
4. Pushes to GHCR as `ghcr.io/rohanbatrain/second_brain_database:dev`

**Duration**: ~5-7 minutes

---

### 5. Build and Push Docker Latest Image (`main.yml`)

**Purpose**: Build and push latest images to registries.

**Triggers**:
- Pushes to `main` branch

**What it does**:
1. Validates docker-compose configuration
2. Builds Docker image
3. Pushes to Docker Hub as `rohanbatra/second_brain_database:latest`
4. Pushes to GHCR as `ghcr.io/rohanbatrain/second_brain_database:latest`

**Duration**: ~5-7 minutes

---

## Required Secrets

See [.github/SECRETS.md](file:///Users/rohan/Documents/repos/second_brain_database/.github/SECRETS.md) for detailed information.

**Required**:
- `DOCKER_HUB_TOKEN`: Docker Hub access token

**Automatic**:
- `GITHUB_TOKEN`: Provided by GitHub Actions

## Manual Workflow Dispatch

You can manually trigger workflows from the GitHub UI:

1. Go to **Actions** tab in your repository
2. Select the workflow you want to run
3. Click **Run workflow**
4. Select the branch
5. Click **Run workflow**

## Viewing Workflow Results

### In Pull Requests

Workflow status checks appear automatically in PRs:
- ✅ Green checkmark: All checks passed
- ❌ Red X: Some checks failed
- 🟡 Yellow dot: Checks in progress

Click on **Details** to view logs.

### In Actions Tab

1. Go to **Actions** tab
2. Click on a workflow run
3. Click on a job to view logs
4. Download artifacts (test results, coverage reports)

## Troubleshooting

### Workflow Fails on "Wait for services to be healthy"

**Cause**: Services taking too long to start or failing health checks.

**Solution**:
1. Check service logs in the workflow output
2. Verify docker-compose configuration locally
3. Increase timeout in workflow if needed

### "Error: Username and password required"

**Cause**: Missing or invalid `DOCKER_HUB_TOKEN` secret.

**Solution**:
1. Verify secret is set in repository settings
2. Check token hasn't expired
3. Regenerate token if necessary

### Tests Fail in CI but Pass Locally

**Cause**: Environment differences or timing issues.

**Solution**:
1. Check if services are fully healthy before tests run
2. Add delays or retries for flaky tests
3. Review test logs for specific failures

### Multi-Platform Build Fails

**Cause**: QEMU or Buildx issues.

**Solution**:
1. Check if both platforms are supported
2. Verify Buildx is properly set up
3. Try building single platform first

## Best Practices

### For Contributors

1. **Always run tests locally** before pushing:
   ```bash
   make docker-test
   ```

2. **Keep PRs focused**: Smaller PRs are easier to test and review

3. **Check workflow status**: Don't merge until all checks pass

4. **Review logs**: If a workflow fails, check the logs before re-running

### For Maintainers

1. **Monitor workflow duration**: Optimize slow workflows

2. **Keep secrets updated**: Rotate tokens regularly

3. **Review security scans**: Address critical vulnerabilities promptly

4. **Update dependencies**: Keep GitHub Actions up to date

## Workflow Optimization

### Caching

Workflows use Docker layer caching to speed up builds:
```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

### Parallel Jobs

Some workflows run jobs in parallel (e.g., multi-platform builds) to reduce total duration.

### Resource Limits

GitHub Actions runners have resource limits:
- 2-core CPU
- 7 GB RAM
- 14 GB SSD

Workflows are optimized to work within these limits.

## Adding New Workflows

To add a new workflow:

1. Create a new `.yml` file in `.github/workflows/`
2. Define triggers, jobs, and steps
3. Test locally with `act` if possible
4. Create a PR to review the workflow
5. Update this documentation

## Monitoring

### Workflow Status Badges

Add status badges to README.md:
```markdown
![Workflow Name](https://github.com/rohanbatrain/second_brain_database/workflows/Workflow%20Name/badge.svg)
```

### Notifications

Configure GitHub notifications:
- Settings → Notifications → Actions
- Choose email or web notifications for workflow failures

## Further Reading

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Docker Compose in CI](https://docs.docker.com/compose/ci/)
