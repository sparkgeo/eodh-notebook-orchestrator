# Enabling Notebook URL Execution in EO DataHub

This document outlines the changes needed to enable URL-based notebook execution in the EO DataHub JupyterHub environment, allowing users to execute notebooks via URLs while maintaining workspace isolation and security.

## Overview

The goal is to integrate the FastAPI-based notebook runner (from this repository) into the existing EO DataHub JupyterHub deployment, enabling users to execute notebooks via URLs like:

```
https://notebook-runner.eodh.com/run/notebook/ndvi_calculation?cog_url=https://example.com/data.tif&bbox=-4.5,53.1,-4.4,53.2
```

## Architecture Changes Required

### 1. New FastAPI Service Deployment

#### A. Create New Docker Image

Build a new Docker image that includes the notebook runner functionality:

```dockerfile
# Dockerfile for notebook-runner service
FROM public.ecr.aws/eodh/eodh-default-notebook:python-3.12-0.2.11

# Install additional dependencies for FastAPI service
RUN pip install \
    fastapi==0.115.14 \
    uvicorn==0.35.0 \
    papermill==2.6.0 \
    pydantic==2.0.0 \
    requests==2.31.0 \
    kubernetes==28.1.0

# Copy notebook runner application
COPY notebook_runner/ /app/notebook_runner/
COPY main.py /app/
COPY pyproject.toml /app/

WORKDIR /app

# Create directories for notebook execution
RUN mkdir -p /app/notebooks /app/templates

# Expose FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### B. Build and Push Image

```bash
# Build the image
docker build -t public.ecr.aws/eodh/eodh-notebook-runner:0.1.0 .

# Push to ECR
docker push public.ecr.aws/eodh/eodh-notebook-runner:0.1.0
```

### 2. Kubernetes Deployment Configuration

#### A. Create Deployment YAML

```yaml
# notebook-runner-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: notebook-runner
  namespace: jupyter
  labels:
    app: notebook-runner
    component: notebook-runner
spec:
  replicas: 2
  selector:
    matchLabels:
      app: notebook-runner
  template:
    metadata:
      labels:
        app: notebook-runner
        component: notebook-runner
    spec:
      serviceAccountName: notebook-runner
      containers:
      - name: notebook-runner
        image: public.ecr.aws/eodh/eodh-notebook-runner:0.1.0
        ports:
        - containerPort: 8000
        env:
        - name: PLATFORM_DOMAIN
          valueFrom:
            configMapKeyRef:
              name: platform-config
              key: PLATFORM_DOMAIN
        - name: WORKSPACES_DOMAIN
          valueFrom:
            configMapKeyRef:
              name: platform-config
              key: WORKSPACES_DOMAIN
        - name: SINGLEUSER_AWS_REGION
          valueFrom:
            configMapKeyRef:
              name: platform-config
              key: SINGLEUSER_AWS_REGION
        - name: SINGLEUSER_AWS_ROLE_ARN
          valueFrom:
            configMapKeyRef:
              name: platform-config
              key: SINGLEUSER_AWS_ROLE_ARN
        - name: SINGLEUSER_WORKSPACE_BUCKET
          valueFrom:
            configMapKeyRef:
              name: platform-config
              key: SINGLEUSER_WORKSPACE_BUCKET
        - name: LOG_LEVEL
          value: "INFO"
        - name: CONFIG_URL
          value: "https://raw.githubusercontent.com/EO-DataHub/notebook-config/main/config.json"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### B. Create Service

```yaml
# notebook-runner-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: notebook-runner
  namespace: jupyter
  labels:
    app: notebook-runner
spec:
  selector:
    app: notebook-runner
  ports:
  - port: 8000
    targetPort: 8000
    protocol: TCP
  type: ClusterIP
```

### 3. Authentication Integration

#### A. Modify FastAPI Application for OIDC

Update the main FastAPI application to integrate with EO DataHub's OIDC authentication:

```python
# main.py modifications
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import requests

security = HTTPBearer()

async def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token from EO DataHub OIDC"""
    try:
        # Get Keycloak public key
        keycloak_url = f"https://{os.getenv('PLATFORM_DOMAIN')}/auth/realms/eodhp"
        jwks_url = f"{keycloak_url}/protocol/openid-connect/certs"
        
        response = requests.get(jwks_url)
        jwks = response.json()
        
        # Verify token
        token = credentials.credentials
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience="eodhp"
        )
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def extract_workspace_from_token(token_payload: dict) -> str:
    """Extract workspace from JWT token claims"""
    workspaces = token_payload.get("workspaces", [])
    if not workspaces:
        raise HTTPException(status_code=403, detail="No workspace access")
    return workspaces[0]  # Use first workspace

@app.get("/run/notebook/{notebook_id}")
async def run_notebook(
    notebook_id: str, 
    request: Request,
    token_payload: dict = Depends(verify_jwt_token)
):
    """Execute notebook with workspace context"""
    try:
        # Extract workspace and user from token
        workspace = extract_workspace_from_token(token_payload)
        user = token_payload.get("preferred_username", "unknown")
        
        # Execute notebook in workspace context
        output_id = execute_notebook_with_workspace(notebook_id, workspace, user, request)
        
        # Redirect to JupyterLab with workspace context
        return RedirectResponse(
            url=f"/view-notebook/{notebook_id}/{output_id}?workspace={workspace}"
        )
        
    except Exception as e:
        logger.error(f"Notebook execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### B. Workspace-Aware Execution

```python
# run_notebook/run_notebook.py modifications
def execute_notebook_with_workspace(notebook_id: str, workspace: str, user: str, request: Request) -> str:
    """Execute notebook with workspace isolation"""
    output_id = str(uuid.uuid4())
    
    # Use workspace-specific S3 path
    s3_key = f"workspaces/{workspace}/notebooks/{user}/{notebook_id}-{output_id}.ipynb"
    local_output_path = f"/tmp/{notebook_id}-{output_id}.ipynb"
    
    try:
        # Get notebook configuration
        notebook = get_notebook_config(notebook_id)
        input_spec = notebook.get("inputSpec", {})
        
        # Parse parameters
        parameters = parse_parameters(request, input_spec)
        
        # Add workspace-specific parameters
        workspace_params = {
            'workspace': workspace,
            'user': user,
            'workspace_s3_bucket': f"workspace-{workspace}",
            'workspace_s3_prefix': f"users/{user}/",
        }
        parameters.update(workspace_params)
        
        # Execute notebook (let Papermill auto-detect kernels)
        pm.execute_notebook(
            notebook["file"],
            local_output_path,
            parameters=parameters,
            prepare_only=True,
        )
        
        # Upload to workspace-specific S3 location
        upload_to_workspace_s3(local_output_path, s3_key, workspace)
        
        # Clean up local file
        os.unlink(local_output_path)
        
        logger.info(f"Notebook {notebook_id} executed successfully for workspace {workspace}")
        return output_id
        
    except Exception as e:
        # Clean up on failure
        if os.path.exists(local_output_path):
            os.unlink(local_output_path)
        logger.error(f"Notebook execution failed: {e}")
        raise

def upload_to_workspace_s3(local_path: str, s3_key: str, workspace: str):
    """Upload notebook to workspace-specific S3 location"""
    import boto3
    
    # Assume workspace-specific role
    sts_client = boto3.client('sts')
    assumed_role = sts_client.assume_role(
        RoleArn=f"arn:aws:iam::account:role/workspace-{workspace}-role",
        RoleSessionName=f"notebook-execution-{workspace}"
    )
    
    # Upload with workspace credentials
    s3_client = boto3.client(
        's3',
        aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
        aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
        aws_session_token=assumed_role['Credentials']['SessionToken']
    )
    
    bucket = f"workspace-{workspace}"
    s3_client.upload_file(local_path, bucket, s3_key)

def get_view_notebook_url(notebook_id: str, output_id: str, workspace: str) -> str:
    """Generate JupyterLab URL with workspace context"""
    platform_domain = os.getenv("PLATFORM_DOMAIN")
    return f"https://{platform_domain}/notebooks/lab/tree/s3/workspaces/{workspace}/notebooks/{notebook_id}-{output_id}.ipynb"
```

### 4. RBAC Configuration

#### A. Service Account

```yaml
# notebook-runner-rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: notebook-runner
  namespace: jupyter
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: notebook-runner
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: notebook-runner
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: notebook-runner
subjects:
- kind: ServiceAccount
  name: notebook-runner
  namespace: jupyter
```

### 5. Ingress Configuration

#### A. Update Ingress for Notebook Runner

```yaml
# notebook-runner-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: notebook-runner-ingress
  namespace: jupyter
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
    nginx.ingress.kubernetes.io/auth-type: jwt
    nginx.ingress.kubernetes.io/auth-url: "https://keycloak.eodh.com/auth/realms/eodhp/protocol/openid-connect/userinfo"
    nginx.ingress.kubernetes.io/auth-signin: "https://keycloak.eodh.com/auth/realms/eodhp/protocol/openid-connect/auth"
spec:
  rules:
  - host: "notebook-runner.{PLATFORM_DOMAIN}"
    http:
      paths:
      - path: /notebook-runner(/|$)(.*)
        pathType: Prefix
        backend:
          service:
            name: notebook-runner
            port:
              number: 8000
```

### 6. Environment-Specific Configuration

#### A. Update values.yaml for each environment

```yaml
# In envs/prod/values.yaml
notebookRunner:
  enabled: true
  image:
    name: public.ecr.aws/eodh/eodh-notebook-runner
    tag: "0.1.0-prod"
  replicas: 3
  ingress:
    host: "notebook-runner.prod.eodh.com"
  environment:
    - name: LOG_LEVEL
      value: "INFO"
    - name: CONFIG_URL
      value: "https://raw.githubusercontent.com/EO-DataHub/notebook-config/main/config.json"
```

#### B. Update kustomization.yaml

```yaml
# In envs/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
- ../../base
- notebook-runner-deployment.yaml
- notebook-runner-service.yaml
- notebook-runner-ingress.yaml
- notebook-runner-rbac.yaml

patches:
- target:
    kind: Deployment
    name: notebook-runner
  patch: |-
    - op: replace
      path: /spec/replicas
      value: 3
    - op: replace
      path: /spec/template/spec/containers/0/env/0/value
      value: "prod.eodh.com"
```

### 7. Integration with Existing JupyterHub

#### A. Add Notebook Runner Links to JupyterHub UI

```python
# In hub.extraConfig
c.JupyterHub.template_vars = {
    'notebook_runner_url': 'https://notebook-runner.{PLATFORM_DOMAIN}/notebook-runner'
}

# Add custom template to show notebook runner links
c.JupyterHub.extra_templates = '/srv/jupyterhub/templates'
```

#### B. Custom Spawn Template Update

```html
<!-- In spawn.html template -->
<div class="notebook-runner-section">
    <h3>Quick Notebook Execution</h3>
    <p>Execute notebooks via URL:</p>
    <div class="example-urls">
        <code>https://notebook-runner.{{ platform_domain }}/notebook-runner/run/notebook/ndvi_calculation?cog_url=YOUR_URL&bbox=min_lon,min_lat,max_lon,max_lat</code>
    </div>
</div>
```

### 8. Monitoring and Observability

#### A. ServiceMonitor for Prometheus

```yaml
# notebook-runner-monitoring.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: notebook-runner-metrics
  namespace: jupyter
spec:
  selector:
    matchLabels:
      app: notebook-runner
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

#### B. Add Metrics to FastAPI Application

```python
# Add to main.py
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('notebook_requests_total', 'Total notebook requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('notebook_request_duration_seconds', 'Request duration')

@app.middleware("http")
async def add_prometheus_metrics(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    REQUEST_DURATION.observe(time.time() - start_time)
    return response

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### 9. Security Considerations

#### A. Network Policies

```yaml
# notebook-runner-network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: notebook-runner-netpol
  namespace: jupyter
spec:
  podSelector:
    matchLabels:
      app: notebook-runner
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 443  # HTTPS for external API calls
    - protocol: TCP
      port: 80   # HTTP for external API calls
  - to:
    - namespaceSelector:
        matchLabels:
          name: jupyter
    ports:
    - protocol: TCP
      port: 8080  # JupyterHub API
```

#### B. Pod Security Policy

```yaml
# notebook-runner-psp.yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: notebook-runner-psp
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
```

### 10. Deployment Steps

#### A. Pre-deployment Checklist

1. **Build and push Docker image** to ECR
2. **Update notebook configuration** repository with new notebook templates
3. **Test authentication integration** with Keycloak
4. **Verify workspace S3 permissions** and bucket access
5. **Update DNS records** for notebook-runner subdomain

#### B. Deployment Process

```bash
# 1. Apply base configuration
kubectl apply -f base/notebook-runner-deployment.yaml
kubectl apply -f base/notebook-runner-service.yaml
kubectl apply -f base/notebook-runner-rbac.yaml

# 2. Apply environment-specific configuration
kubectl apply -k envs/prod/

# 3. Verify deployment
kubectl get pods -n jupyter -l app=notebook-runner
kubectl logs -n jupyter -l app=notebook-runner

# 4. Test functionality
curl -H "Authorization: Bearer $JWT_TOKEN" \
     "https://notebook-runner.prod.eodh.com/notebook-runner/health"
```

#### C. Post-deployment Verification

1. **Health check endpoint** responds correctly
2. **Authentication integration** works with existing OIDC
3. **Workspace isolation** is maintained
4. **Notebook execution** works with available kernels
5. **S3 upload** to workspace-specific buckets succeeds
6. **JupyterLab redirect** opens executed notebooks correctly

### 11. Troubleshooting Guide

#### A. Common Issues

**Issue**: Notebook execution fails with kernel errors
**Solution**: Ensure the default notebook image has required packages installed

**Issue**: S3 upload fails with permission errors
**Solution**: Verify IAM role permissions for workspace buckets

**Issue**: Authentication fails
**Solution**: Check Keycloak configuration and JWT token validation

**Issue**: Redirect to JupyterLab fails
**Solution**: Verify JupyterLab URL format and workspace paths

#### B. Debug Commands

```bash
# Check pod status
kubectl describe pod -n jupyter -l app=notebook-runner

# Check logs
kubectl logs -n jupyter -l app=notebook-runner --tail=100

# Test internal connectivity
kubectl exec -n jupyter -l app=notebook-runner -- curl localhost:8000/health

# Check service endpoints
kubectl get endpoints -n jupyter notebook-runner
```

### 12. Future Enhancements

#### A. Planned Improvements

1. **Kernel selection UI** - Allow users to specify preferred kernels
2. **Batch execution** - Support multiple notebook execution
3. **Progress tracking** - Real-time execution status updates
4. **Custom parameters UI** - Web form for parameter input
5. **Execution history** - Track and display past executions
6. **Workspace templates** - Pre-configured notebook templates per workspace

#### B. Performance Optimizations

1. **Caching** - Cache notebook configurations and results
2. **Parallel execution** - Support concurrent notebook execution
3. **Resource limits** - Implement execution time and resource limits
4. **Cleanup jobs** - Automatic cleanup of old execution results

This implementation provides a robust, secure, and scalable solution for URL-based notebook execution while maintaining the existing EO DataHub architecture and security model.
