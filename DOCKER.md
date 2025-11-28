# Docker Image Publishing Guide

This guide covers building and publishing the LogCost sidecar Docker image to Docker Hub or other registries.

## Prerequisites

1. Docker installed and running
2. Docker Hub account (or other registry account)
3. Logged in to Docker Hub: `docker login`

## Building the Image

From the LogCost root directory:

```bash
# Build for your local architecture
docker build -t logcost/logcost:latest .

# Build for multiple architectures (arm64, amd64)
docker buildx build --platform linux/amd64,linux/arm64 -t logcost/logcost:latest .
```

Test the image locally:

```bash
docker run --rm logcost/logcost:latest python --version
docker run --rm logcost/logcost:latest python -c "import logcost; print('LogCost imported successfully')"
```

## Publishing to Docker Hub

### Option 1: Manual Publishing (Quick Start)

```bash
# Build and tag
docker build -t logcost/logcost:latest .

# Also tag with version
docker tag logcost/logcost:latest logcost/logcost:v0.1.0

# Push to Docker Hub
docker push logcost/logcost:latest
docker push logcost/logcost:v0.1.0
```

### Option 2: Multi-Architecture Build (Recommended)

Build images that work on both Intel/AMD (amd64) and ARM (arm64) platforms:

```bash
# Create and use buildx builder
docker buildx create --name multiarch --use
docker buildx inspect --bootstrap

# Build and push for multiple architectures
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t logcost/logcost:latest \
  -t logcost/logcost:v0.1.0 \
  --push \
  .
```

### Option 3: Automated GitHub Actions (Best for Open Source)

Create `.github/workflows/docker-publish.yml`:

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [ master ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ master ]

env:
  REGISTRY: docker.io
  IMAGE_NAME: logcost/logcost

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Log into Docker Hub
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=sha

      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Then configure GitHub secrets:
- Go to Settings → Secrets and variables → Actions
- Add `DOCKERHUB_USERNAME` (your Docker Hub username)
- Add `DOCKERHUB_TOKEN` (create at https://hub.docker.com/settings/security)

## Versioning Strategy

Use semantic versioning (SemVer):

```bash
# Development builds
docker tag logcost/logcost:latest logcost/logcost:dev

# Release candidates
docker tag logcost/logcost:latest logcost/logcost:v0.1.0-rc1

# Stable releases
docker tag logcost/logcost:latest logcost/logcost:v0.1.0
docker tag logcost/logcost:latest logcost/logcost:0.1
docker tag logcost/logcost:latest logcost/logcost:0

# Push all tags
docker push logcost/logcost:latest
docker push logcost/logcost:v0.1.0
docker push logcost/logcost:0.1
docker push logcost/logcost:0
```

**Recommended tagging convention:**
- `latest` - most recent stable release
- `v0.1.0` - specific version (full semver)
- `0.1` - minor version (gets latest patch)
- `0` - major version (gets latest minor.patch)
- `dev` - development/unstable builds

## Publishing to Other Registries

### Google Container Registry (GCR)

```bash
# Authenticate with GCR
gcloud auth configure-docker

# Tag and push
docker tag logcost/logcost:latest gcr.io/PROJECT_ID/logcost:latest
docker push gcr.io/PROJECT_ID/logcost:latest
```

### Amazon ECR

```bash
# Authenticate with ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Create repository (first time only)
aws ecr create-repository --repository-name logcost

# Tag and push
docker tag logcost/logcost:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/logcost:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/logcost:latest
```

### Azure Container Registry (ACR)

```bash
# Authenticate with ACR
az acr login --name myregistry

# Tag and push
docker tag logcost/logcost:latest myregistry.azurecr.io/logcost:latest
docker push myregistry.azurecr.io/logcost:latest
```

### GitHub Container Registry (GHCR)

```bash
# Authenticate with GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Tag and push
docker tag logcost/logcost:latest ghcr.io/USERNAME/logcost:latest
docker push ghcr.io/USERNAME/logcost:latest
```

## Image Size Optimization

The current Dockerfile is already optimized with:
- `python:3.11-slim` base (smaller than full Python image)
- `--no-cache-dir` for pip installs
- Cleanup of pip cache
- No dev dependencies

Current size: ~150-200MB (depending on architecture)

Further optimization options:
- Use `python:3.11-alpine` for ~50-70MB (but may have compatibility issues)
- Multi-stage build (if needed in the future)

## Security Scanning

Scan images for vulnerabilities before publishing:

```bash
# Using Docker Scout (built-in)
docker scout cves logcost/logcost:latest

# Using Trivy
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image logcost/logcost:latest

# Using Snyk
snyk container test logcost/logcost:latest
```

## Updating Kubernetes Deployments

After publishing a new version, update your Kubernetes deployment:

```bash
# Update to specific version
kubectl set image deployment/myapp-with-logcost \
  logcost-sidecar=logcost/logcost:v0.2.0

# Or use image pull policy to always get latest
# (set in deployment.yaml: imagePullPolicy: Always)
kubectl rollout restart deployment/myapp-with-logcost
```

## Testing Published Images

Test the published image works correctly:

```bash
# Test on Kubernetes
kubectl run logcost-test \
  --image=logcost/logcost:latest \
  --rm -it --restart=Never \
  -- python -c "import logcost; print('Success')"

# Test locally with environment
docker run --rm \
  -e LOGCOST_SLACK_WEBHOOK=https://hooks.slack.com/test \
  -e LOGCOST_PROVIDER=gcp \
  logcost/logcost:latest \
  python -c "import os; from logcost import sidecar; print('Config OK')"
```

## Troubleshooting

**Issue: "denied: requested access to the resource is denied"**
- Solution: Run `docker login` and ensure you have push permissions

**Issue: Multi-arch build fails**
- Solution: Ensure buildx is set up: `docker buildx create --use`

**Issue: Image is too large**
- Check layers: `docker history logcost/logcost:latest`
- Ensure pip cache is cleaned in Dockerfile

**Issue: Import errors in container**
- Verify all dependencies in setup.py are installed
- Test with: `docker run --rm IMAGE python -c "import logcost"`

## Next Steps

Once the image is published:

1. Update Kubernetes manifests to use your registry
2. Set up automated builds on git tags
3. Add security scanning to CI/CD
4. Document the public image in README for users
5. Consider image signing for production use

## Quick Reference

```bash
# Build
docker build -t logcost/logcost:v0.1.0 .

# Tag
docker tag logcost/logcost:v0.1.0 logcost/logcost:latest

# Push
docker push logcost/logcost:v0.1.0
docker push logcost/logcost:latest

# Multi-arch (all in one)
docker buildx build --platform linux/amd64,linux/arm64 \
  -t logcost/logcost:latest \
  -t logcost/logcost:v0.1.0 \
  --push .
```
