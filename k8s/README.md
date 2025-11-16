# Mockbin Kubernetes/OpenShift Manifests

This directory contains production-ready Kubernetes/OpenShift manifests for deploying the mockbin application with full OpenShift integration.

## Contents

### Core Resources
- **namespace.yaml** - Creates the `mockbin` namespace with OpenShift metadata
- **serviceaccount.yaml** - Dedicated ServiceAccount for the application
- **deployment.yaml** - Deploys 2 replicas with OpenShift-specific annotations
- **service.yaml** - ClusterIP service with automatic TLS certificate generation

### OpenShift-Specific
- **route.yaml** - OpenShift Route with TLS edge termination and rate limiting
- **ingress.yaml** - Alternative Ingress for standard Kubernetes (not used on OpenShift)

### High Availability & Scaling
- **hpa.yaml** - HorizontalPodAutoscaler (2-10 replicas based on CPU/memory)
- **pdb.yaml** - PodDisruptionBudget ensuring minimum availability during updates

### Security
- **networkpolicy.yaml** - NetworkPolicy controlling ingress/egress traffic

### Utilities
- **kustomization.yaml** - Kustomize configuration for easy deployment
- **update-version.sh** - Script to update image versions

## Deployment Options

### Option 1: Deploy on OpenShift (Recommended)

The manifests are fully optimized for OpenShift with:
- ✅ OpenShift Routes with TLS and rate limiting
- ✅ ServiceAccount with OAuth integration ready
- ✅ Automatic TLS certificate generation for services
- ✅ OpenShift-specific labels and annotations
- ✅ NetworkPolicy for pod-to-pod communication
- ✅ HorizontalPodAutoscaler for automatic scaling
- ✅ PodDisruptionBudget for high availability

**Deploy using Kustomize (Recommended):**
```bash
# Deploy everything at once
kubectl apply -k .

# Or using oc CLI
oc apply -k .
```

**Or deploy individual files:**
```bash
oc apply -f namespace.yaml
oc apply -f serviceaccount.yaml
oc apply -f deployment.yaml
oc apply -f service.yaml
oc apply -f route.yaml
oc apply -f hpa.yaml
oc apply -f pdb.yaml
oc apply -f networkpolicy.yaml
```

**Get the route URL:**
```bash
oc get route mockbin -n mockbin -o jsonpath='{.spec.host}'

# Or with full details
oc get route mockbin -n mockbin
```

**Access the application:**
```bash
ROUTE_URL=$(oc get route mockbin -n mockbin -o jsonpath='{.spec.host}')
curl https://$ROUTE_URL
```

### Option 2: Deploy on Standard Kubernetes

Uses Kubernetes Ingress instead of Route:

1. Edit `kustomization.yaml`:
   - Comment out `route.yaml`
   - Uncomment `ingress.yaml`

2. Edit `ingress.yaml`:
   - Set your domain in `spec.rules[].host`
   - Configure TLS if needed
   - Adjust ingress class and annotations

3. Deploy:
```bash
kubectl apply -k .
```

### Option 3: Deploy Individual Manifests

```bash
kubectl apply -f namespace.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
# Then either:
kubectl apply -f route.yaml      # For OpenShift
# OR
kubectl apply -f ingress.yaml    # For Kubernetes
```

## Configuration

### Update Image Version

Edit `kustomization.yaml` and change the image tag:

```yaml
images:
  - name: quay.io/tjungbau/mockbin
    newTag: 1.0.1  # Change this
```

Or edit `deployment.yaml` directly:

```yaml
spec:
  template:
    spec:
      containers:
      - name: mockbin
        image: quay.io/tjungbau/mockbin:1.0.1  # Change this
```

### Adjust Resources

Edit `deployment.yaml` to modify CPU/memory requests and limits:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### Scale Replicas

```bash
# Scale to 3 replicas
kubectl scale deployment mockbin -n mockbin --replicas=3

# Or edit deployment.yaml
spec:
  replicas: 3
```

## Verification

### Check Deployment Status

```bash
# Check all resources
kubectl get all -n mockbin

# Check deployment
kubectl get deployment mockbin -n mockbin

# Check pods
kubectl get pods -n mockbin

# Check service
kubectl get svc mockbin -n mockbin

# Check route (OpenShift)
oc get route mockbin -n mockbin

# Check ingress (Kubernetes)
kubectl get ingress mockbin -n mockbin
```

### View Logs

```bash
# View logs from all pods
kubectl logs -l app=mockbin -n mockbin

# Follow logs
kubectl logs -f -l app=mockbin -n mockbin

# Logs from specific pod
kubectl logs mockbin-xxxxx-yyyyy -n mockbin
```

### Test the Application

```bash
# Port forward (for testing without route/ingress)
kubectl port-forward svc/mockbin 8080:8080 -n mockbin

# Test locally
curl http://localhost:8080

# Test via route (OpenShift)
ROUTE_URL=$(oc get route mockbin -n mockbin -o jsonpath='{.spec.host}')
curl https://$ROUTE_URL

# Test via ingress (Kubernetes)
curl https://mockbin.example.com
```

## Troubleshooting

### Pods not starting

```bash
# Describe pod to see events
kubectl describe pod mockbin-xxxxx-yyyyy -n mockbin

# Check logs
kubectl logs mockbin-xxxxx-yyyyy -n mockbin
```

### Image pull errors

Verify the image exists:
```bash
podman pull quay.io/tjungbau/mockbin:1.0.0
```

### Service not accessible

```bash
# Check endpoints
kubectl get endpoints mockbin -n mockbin

# Test from within cluster
kubectl run -it --rm debug --image=busybox -n mockbin -- wget -O- http://mockbin:8080
```

## Clean Up

```bash
# Delete using kustomize
kubectl delete -k .

# Or delete individual resources
kubectl delete -f route.yaml
kubectl delete -f service.yaml
kubectl delete -f deployment.yaml
kubectl delete -f namespace.yaml
```

## OpenShift-Specific Features

### 1. OpenShift Route Configuration
The Route includes:
- **TLS edge termination** - SSL/TLS handled by OpenShift router
- **Automatic HTTPS redirect** - HTTP traffic redirected to HTTPS
- **Rate limiting** - 100 concurrent connections, 100 connections/sec
- **Timeout configuration** - 60s timeout for long-running requests

### 2. Automatic Service Certificates
The Service is annotated to automatically generate TLS certificates:
```yaml
annotations:
  service.alpha.openshift.io/serving-cert-secret-name: mockbin-tls
```
OpenShift automatically creates a `mockbin-tls` secret with certificates.

### 3. Deployment Topology View
OpenShift annotations enable the Topology view to show:
- **Runtime icon** - Python runtime badge
- **VCS integration** - Links to source repository
- **Image triggers** - Can be configured for ImageStream updates

### 4. ServiceAccount Integration
- Dedicated ServiceAccount for the application
- OAuth redirect reference configured
- Can be extended with additional RBAC roles

### 5. NetworkPolicy
Controls traffic flow:
- **Ingress**: Only from OpenShift router and same namespace
- **Egress**: DNS, HTTPS, and Kubernetes API access
- Blocks all other traffic by default

### 6. HorizontalPodAutoscaler
Automatically scales based on:
- **CPU utilization** - Target: 70%
- **Memory utilization** - Target: 80%
- **Replica range** - 2 to 10 pods
- **Scale-up policy** - Fast scaling (100% or 4 pods per 15s)
- **Scale-down policy** - Conservative (50% per 15s with 5min stabilization)

### 7. PodDisruptionBudget
Ensures high availability during:
- Node maintenance
- Cluster upgrades
- Rolling updates
- **Minimum available** - Always keeps at least 1 pod running

## Security Features

- ✅ OpenShift SCC automatically applied (restricted-v2 by default)
- ✅ Runs as non-root user (assigned by OpenShift SCC)
- ✅ Security context managed by OpenShift
- ✅ Includes liveness and readiness probes
- ✅ Resource limits enforced
- ✅ TLS termination at edge (Route)
- ✅ NetworkPolicy restricts traffic
- ✅ Dedicated ServiceAccount (non-default)
- ✅ Image built with minimal attack surface (UBI10)

## Quick Reference - OpenShift Commands

### Deploy
```bash
# Deploy everything
oc apply -k k8s/

# Watch deployment progress
oc get pods -n mockbin -w
```

### Access Application
```bash
# Get route URL
oc get route mockbin -n mockbin

# Test the application
curl https://$(oc get route mockbin -n mockbin -o jsonpath='{.spec.host}')
```

### Monitoring
```bash
# View all resources
oc get all -n mockbin

# Check HPA status
oc get hpa mockbin -n mockbin

# View logs
oc logs -f deployment/mockbin -n mockbin

# View recent events
oc get events -n mockbin --sort-by='.lastTimestamp'
```

### Scaling
```bash
# Manual scale
oc scale deployment mockbin --replicas=3 -n mockbin

# Check autoscaler status
oc describe hpa mockbin -n mockbin
```

### Troubleshooting
```bash
# Describe pod
oc describe pod <pod-name> -n mockbin

# Get pod logs
oc logs <pod-name> -n mockbin

# Shell into pod
oc rsh <pod-name> -n mockbin

# Check service endpoints
oc get endpoints mockbin -n mockbin

# Test service from within cluster
oc run debug -it --rm --image=registry.access.redhat.com/ubi9/ubi-minimal -- curl http://mockbin.mockbin.svc:8080
```

### Updates
```bash
# Update image version
cd k8s
./update-version.sh 1.0.1

# Apply changes
oc apply -k .

# Watch rollout
oc rollout status deployment/mockbin -n mockbin

# Rollback if needed
oc rollout undo deployment/mockbin -n mockbin
```

### Cleanup
```bash
# Delete everything
oc delete -k k8s/

# Or delete namespace (removes everything)
oc delete namespace mockbin
```

## Architecture

```
Internet
   ↓
OpenShift Router (TLS termination, rate limiting)
   ↓
Route: mockbin (edge TLS)
   ↓
Service: mockbin:8080 (ClusterIP, auto TLS cert)
   ↓
Deployment: mockbin (2-10 replicas via HPA)
   ├─ Pod: mockbin-xxx (Python app on port 8080)
   ├─ Pod: mockbin-yyy (Python app on port 8080)
   └─ ...
   
Protected by:
- NetworkPolicy (ingress/egress rules)
- PodDisruptionBudget (min 1 available)
- ServiceAccount (mockbin)
- OpenShift SCC (restricted-v2, auto-applied)
```

