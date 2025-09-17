# Jupyter Notebook Configuration Guide for EO DataHub

This document provides comprehensive instructions for understanding and working with the Jupyter notebook configuration in the EO DataHub ArgoCD deployment.

## Overview

The JupyterHub deployment in EO DataHub provides server-side notebooks scoped to workspaces with custom authentication and AWS integration. The configuration uses Kubernetes, Helm, and Kustomize for deployment management.

## Architecture Components

### 1. Core Infrastructure

- **Namespace**: `jupyter` (with Linkerd service mesh injection)
- **Helm Chart**: JupyterHub v4.2.0 from official repository
- **Custom Images**: Built in `public.ecr.aws/eodh/` registry
- **Authentication**: Custom OIDC authenticator with workspace scoping

### 2. Key Configuration Files

#### `kustomization.yaml` (Base)

- Defines namespace, resources, and Helm chart configuration
- Applies patches to prevent unnecessary redeployments
- Configures secret generation with automatic token creation
- Uses JupyterHub Helm chart version 4.2.0

#### `values.yaml` (Helm Configuration)

- **Hub Configuration**: Custom EODH JupyterHub image with OIDC authentication
- **Single User Configuration**: Custom notebook images with EO data analysis tools
- **Environment Variables**: Platform domains, AWS settings, OAuth secrets
- **Extra Config**: Python configuration files executed on startup
- **Custom Templates**: HTML templates for spawn page customization

#### `config.yaml` (Environment Variables)

- Platform and workspace domain configuration
- AWS region and role ARN for single user pods
- S3 workspace bucket configuration
- Custom HTML template for workspace selection

#### `ingress.yaml` (Network Access)

- NGINX ingress configuration for `/notebooks` path
- WebSocket support for real-time notebook interaction
- Custom header guards and authentication bypass

#### `aws-roles.yaml` (AWS Integration)

- IAM role for Jupyter single user pods
- OIDC trust relationship with Keycloak
- S3 access policies scoped to user workspaces

## Authentication Flow

### 1. OIDC Integration

- **Authenticator**: Custom `EODHAuthenticator` class
- **Provider**: Keycloak with `eodhp` realm
- **Scopes**: `openid` and `workspaces`
- **Token Exchange**: JWT tokens exchanged for workspace-scoped tokens

### 2. Workspace Scoping

- Users select from available workspaces during spawn
- Each workspace gets isolated S3 bucket access
- Workspace selection stored in auth state
- Custom spawner validates workspace access

### 3. AWS Integration

- Single user pods assume IAM roles via OIDC
- S3 access limited to workspace-specific prefixes
- Automatic token refresh for long-running sessions

## Data Storage Architecture

### 1. Hybrid Contents Manager

- **EFS Mount**: User's root drive for persistent storage
- **S3 Mount**: Virtual drive at `/s3` for workspace data
- **S3 Requirements**: Directories need `.s3keep` files for proper display
- **Lambda Integration**: Automatic `.s3keep` file creation

### 2. Workspace Isolation

- Each workspace gets separate S3 bucket prefix
- User namespaces: `ws-{workspace}`
- PVC naming: `pvc-{workspace}`
- Pod naming: `jupyter-{username}`

## Custom Configuration

### 1. Hub Extra Config Files

Configuration is applied through Python files in `hub.extraConfig`:

- **`1_configure_jupyterhub.py`**: Basic JupyterHub settings
- **`2_configure_authenticator.py`**: OIDC authentication setup
- **`3_configure_spawner.py`**: Custom spawner with token exchange

### 2. Custom Templates

- **`spawn.html`**: Custom workspace selection interface
- **Template Path**: `/srv/jupyterhub/templates`
- **Features**: Workspace dropdown, error handling, feedback widgets

### 3. Notebook Profiles

Three available profiles:

- **EO DataHub**: Custom image with EO analysis tools (default)
- **Python 3.12**: Standard Jupyter base image
- **R 4.4**: R notebook environment

## Environment-Specific Deployments

### Environment Structure

```
envs/
├── dev/
├── dev3/
├── prod/
├── staging/
└── test/
```

Each environment inherits from base configuration with potential overrides.

## Security Considerations

### 1. RBAC Configuration

- **ClusterRole**: `hub` with pod, namespace, PVC management
- **Permissions**: Create, delete, get, watch, list resources
- **Service Account**: `hub` in `jupyter` namespace

### 2. Secret Management

- **External Secrets**: Integration with AWS Secrets Manager
- **Auto-Generated**: Hub tokens, proxy secrets, cookie secrets
- **Refresh Interval**: 1 minute for OAuth client secrets

### 3. Network Security

- **Ingress**: NGINX with custom header guards
- **WebSocket**: Supported for real-time features
- **Auth Bypass**: Authentication handled by JupyterHub

## Troubleshooting Guide

### 1. Common Issues

- **Workspace Selection**: Ensure OIDC claims include workspaces
- **S3 Mount Issues**: Check `.s3keep` files in S3 prefixes
- **Token Exchange**: Verify OAuth client secrets are correct
- **Pod Spawning**: Check IAM role permissions and OIDC trust

### 2. Debug Configuration

- **Debug Mode**: Enabled in values.yaml
- **Logging**: Check hub and spawner logs
- **Auth State**: Verify workspace claims in user tokens

### 3. Monitoring

- **Pod Status**: Monitor user pod creation and health
- **Resource Usage**: Check node affinity and resource limits
- **Network**: Verify ingress and service connectivity

## Customization Points

### 1. Adding New Notebook Images

1. Build custom image in `eodh-jupyter-images` repository
2. Update `profileList` in `values.yaml`
3. Configure any required environment variables

### 2. Modifying Authentication

1. Update authenticator configuration in `2_configure_authenticator.py`
2. Adjust OIDC scopes and claims as needed
3. Update workspace validation logic

### 3. Customizing UI

1. Modify templates in `hub-templates` ConfigMap
2. Update CSS and JavaScript in spawn template
3. Add new template files as needed

## Dependencies

### External Repositories

- **Jupyter Images**: `https://github.com/EO-DataHub/eodh-jupyter-images`
- **Auth Plugin**: `https://github.com/EO-DataHub/eodh-jpyauth`
- **Helm Chart**: `https://hub.jupyter.org/helm-chart/`

### AWS Resources

- **ECR Registry**: `public.ecr.aws/eodh/`
- **S3 Buckets**: Workspace-specific buckets
- **IAM Roles**: OIDC trust relationships
- **Lambda Functions**: S3 event processing

## Configuration Variables

### Required Environment Variables

- `PLATFORM_DOMAIN`: Main platform domain
- `WORKSPACES_DOMAIN`: Workspaces subdomain
- `SINGLEUSER_AWS_REGION`: AWS region for single user pods
- `SINGLEUSER_AWS_ROLE_ARN`: IAM role for workspace access
- `SINGLEUSER_WORKSPACE_BUCKET`: S3 bucket for workspace data

### OAuth Configuration

- `OAUTH_CLIENT_SECRET`: Jupyter OIDC client secret
- `WORKSPACES_CLIENT_SECRET`: Workspaces service client secret

This configuration provides a robust, secure, and scalable Jupyter notebook environment with workspace isolation and AWS integration for the EO DataHub platform.

## Image Build and Deployment Process

This section explains how to build and deploy the custom Jupyter images used in the EO DataHub platform, based on the contents of this repository.

### Repository Structure

The `eodh-jupyter-images` repository contains two main image types:

```
eodh-jupyter-images/
├── default/          # User notebook server image
│   ├── Dockerfile
│   ├── Makefile
│   ├── README.md
│   └── jupyter_server_config.py
├── hub/              # JupyterHub server image
│   ├── Dockerfile
│   └── Makefile
└── README.md
```

### 1. Default Notebook Server Image

#### Purpose

The default image (`public.ecr.aws/eodh/eodh-default-notebook`) serves as the primary user notebook environment with EO data analysis capabilities.

#### Base Image

- **Source**: `quay.io/jupyter/base-notebook:python-3.12`
- **Python Version**: 3.12
- **User**: `jovyan` (Jupyter standard)

#### Key Components

**System Dependencies:**

- `curl`, `git`, `nano`, `unzip` for development tools
- AWS CLI v2 for S3 integration

**Python Packages:**

- **Core Jupyter**: `jupyterlab==4.4.0`, `jupyterlab-git==0.51.1`
- **EO Data Analysis**: `pyeodh==0.1.4`, `shapely==2.0.7`, `geopandas==1.0.1`
- **AWS Integration**: `boto3==1.37.1`
- **File Management**: `s3contents==0.11.2`, `hybridcontents==0.4.0`
- **Utilities**: `python-dotenv==1.0.1`

**Configuration:**

- Custom `jupyter_server_config.py` copied to `/etc/jupyter/`
- HybridContentsManager for dual file system support (local + S3)

#### Build Process

```bash
cd default
make container-build
make container-push
```

**Makefile Variables:**

- `image`: `public.ecr.aws/eodh/eodh-default-notebook`
- `version`: `python-3.12-0.2.11` (configurable)
- `docker`: `docker` (configurable)

### 2. JupyterHub Server Image

#### Purpose

The hub image (`public.ecr.aws/eodh/eodh-jupyter-hub`) provides the JupyterHub server with custom authentication and AWS integration.

#### Base Image

- **Source**: `quay.io/jupyterhub/k8s-hub:4.2.0`
- **JupyterHub Version**: 4.2.0

#### Key Components

**Python Packages:**

- `boto3==1.37.20` for AWS integration
- `eodh-jpyauth==0.1.3` for custom OIDC authentication

**Configuration:**

- Uses standard JupyterHub configuration from `/srv/jupyterhub/jupyterhub_config.py`
- Custom authenticator and spawner logic loaded via Helm values

#### Build Process

```bash
cd hub
make container-build
make container-push
```

**Makefile Variables:**

- `image`: `public.ecr.aws/eodh/eodh-jupyter-hub`
- `version`: `4.2.0-0.2.0` (configurable)

### 3. Image Configuration Details

#### Default Image S3 Integration

The default image uses a sophisticated file management system:

**HybridContentsManager Setup:**

- **Root Directory**: `/home/jovyan` (local file system)
- **S3 Mount**: Virtual drive at `/s3` prefix
- **Manager Classes**:
  - `""` (root): `LargeFileManager` for local files
  - `"s3"`: `S3ContentsManager` for workspace data

**Environment Variables Required:**

- `JUPYTERHUB_USER`: Current user identifier
- `S3CONTENTS_AWS_REGION`: AWS region for S3 access
- `S3CONTENTS_AWS_ROLE_ARN`: IAM role for workspace access
- `S3CONTENTS_WORKSPACE_ACCESS_TOKEN`: OIDC token for role assumption
- `S3CONTENTS_WORKSPACE_BUCKET`: S3 bucket name
- `WORKSPACE`: Workspace identifier for S3 prefix

**Security Features:**

- Automatic IAM role assumption using OIDC tokens
- Workspace-scoped S3 access via prefix isolation
- Server-side encryption (AES256) for S3 objects
- S3v4 signature version for secure API calls

### 4. Build and Release Workflow

#### Version Management

1. **Update Version Numbers:**
   - Edit `Makefile` in each directory
   - Update `version` variable with new semantic version
   - Follow format: `python-3.12-0.2.11` or `4.2.0-0.2.0`

2. **Build Images:**

   ```bash
   # Build both images
   cd default && make container-build
   cd ../hub && make container-build
   ```

3. **Push to Registry:**

   ```bash
   # Push both images
   cd default && make container-push
   cd ../hub && make container-push
   ```

4. **Tag Release:**

   ```bash
   # Create and push tags
   git tag default-python-3.12-0.2.11
   git tag hub-4.2.0-0.2.0
   git push origin --tags
   ```

#### Registry Configuration

- **Registry**: `public.ecr.aws/eodh/`
- **Images**:
  - `eodh-default-notebook:python-3.12-0.2.11`
  - `eodh-jupyter-hub:4.2.0-0.2.0`

### 5. Integration with ArgoCD Deployment

#### Image References in Helm Values

The built images are referenced in the JupyterHub Helm values:

```yaml
hub:
  image:
    name: public.ecr.aws/eodh/eodh-jupyter-hub
    tag: 4.2.0-0.2.0

singleuser:
  image:
    name: public.ecr.aws/eodh/eodh-default-notebook
    tag: python-3.12-0.2.11
```

#### Deployment Process

1. **Build and Push Images** (this repository)
2. **Update Helm Values** (ArgoCD configuration)
3. **Deploy via ArgoCD** (automatic sync or manual sync)

### 6. Development and Testing

#### Local Development

```bash
# Build image locally for testing
cd default
make container-build

# Run container for testing
docker run -it --rm \
  -e JUPYTERHUB_USER=testuser \
  -e WORKSPACE=test-workspace \
  -e S3CONTENTS_AWS_REGION=us-east-1 \
  -e S3CONTENTS_AWS_ROLE_ARN=arn:aws:iam::123456789012:role/test-role \
  -e S3CONTENTS_WORKSPACE_ACCESS_TOKEN=test-token \
  -e S3CONTENTS_WORKSPACE_BUCKET=test-bucket \
  public.ecr.aws/eodh/eodh-default-notebook:python-3.12-0.2.11
```

#### Testing S3 Integration

The S3 integration can be tested by providing valid AWS credentials and workspace tokens. The `configure_s3_contents_manager()` function will automatically set up the S3 mount if all required environment variables are present.

### 7. Troubleshooting Image Builds

#### Common Issues

1. **Build Failures:**
   - Check Docker daemon is running
   - Verify base image availability
   - Check network connectivity for package downloads

2. **Push Failures:**
   - Verify AWS ECR authentication
   - Check registry permissions
   - Ensure image tags are unique

3. **Runtime Issues:**
   - Verify environment variables are set
   - Check IAM role permissions
   - Validate OIDC token format

#### Debug Commands

```bash
# Check image layers
docker history public.ecr.aws/eodh/eodh-default-notebook:python-3.12-0.2.11

# Inspect image contents
docker run --rm -it public.ecr.aws/eodh/eodh-default-notebook:python-3.12-0.2.11 /bin/bash

# Check configuration
docker run --rm public.ecr.aws/eodh/eodh-default-notebook:python-3.12-0.2.11 cat /etc/jupyter/jupyter_server_config.py
```

This image build and deployment process ensures that the EO DataHub Jupyter environment has the necessary tools and configurations for effective Earth Observation data analysis with secure AWS integration.
