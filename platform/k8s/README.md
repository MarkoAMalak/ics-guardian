# Kubernetes Deployment

Two ways to deploy the detector to a cluster — plain manifests or a Helm chart.

## Option A — plain manifests

```bash
# one-time: the JWT signing key the pods read from a Secret
kubectl create secret generic ics-detector-auth --from-literal=secret=$(openssl rand -hex 32)
kubectl apply -f k8s/
kubectl get pods -l app=ics-detector
kubectl port-forward svc/ics-detector 8000:80
curl http://localhost:8000/health
```

Included:

- `deployment.yaml` — Deployment (2 replicas, hardened `securityContext`, liveness/
  readiness probes, resource requests/limits) + ClusterIP Service.
- `hpa.yaml` — HorizontalPodAutoscaler (2→6 replicas at 70% CPU) — the elasticity
  that backs the "cloud-native" claim.

## Option B — Helm chart

```bash
helm install ics ./helm/ics-detector
# override anything:
helm install ics ./helm/ics-detector \
  --set replicaCount=3 --set autoscaling.enabled=false --set image.tag=1.1.0
helm upgrade ics ./helm/ics-detector -f my-values.yaml
```

The chart (`helm/ics-detector`) parameterizes image, replicas, resources,
autoscaling, security context, and Prometheus annotations via `values.yaml`.

## Security posture (why this maps to DevSecOps)

Every pod runs **non-root** (uid 10001), **read-only root filesystem**, **all Linux
capabilities dropped**, `allowPrivilegeEscalation: false`, and the
`RuntimeDefault` seccomp profile — the same hardening the CI/CD Trivy config-scan
enforces on the image. Because the root filesystem is read-only, the SQLite user store
(`/app/data`) and `/tmp` are small writable `emptyDir` volumes; the model artifacts are
baked into the scanned image (the Helm chart can mount a PVC over them via
`artifacts.existingClaim`). The user store is per pod, so with several replicas use a
shared identity store for real logins.

## Building the image first

```bash
docker build -t ics-detector:1.0.0 detection_service
# load it into your local cluster, e.g. for kind:
kind load docker-image ics-detector:1.0.0
```
