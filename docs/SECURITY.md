# 🔒 Security Guide

## Overview

AutoScaleOps uses multiple layers of security to protect your data and infrastructure.

---

## Secret Storage

### Windows Credential Manager (Primary)
API keys and tokens are stored in Windows Credential Manager — the same place Windows stores your browser passwords.

```python
from core.security import SecretManager

secrets = SecretManager()

# Store API key securely
secrets.store_secret('cloudflare_token', 'your-token-here')

# Retrieve it later
token = secrets.get_secret('cloudflare_token')
```

**To view stored secrets:**
- Open: Control Panel → Credential Manager → Windows Credentials
- Look for entries starting with `AutoScaleOps`

### Encrypted File Storage (Fallback)
If keyring is unavailable, secrets are stored in `~/.autoscaleops/.secrets` encrypted with AES-256.

---

## Configuration Encryption

All configuration is stored encrypted in `~/.autoscaleops/config.enc`:

- **Algorithm:** AES-256 (via Fernet)
- **Key derivation:** PBKDF2-SHA256 (100,000 iterations)
- **Key material:** MAC address + hostname (machine-specific)
- **Result:** Config is unreadable on other machines

---

## Kubernetes Security

### Namespace Isolation
Each installation gets an isolated namespace:
```
autoscaleops-{unique_id}
```
Pods in one namespace cannot access pods in another.

### Non-root Containers
All Docker images run as non-root users:
```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```

### Resource Limits
All pods have CPU and memory limits to prevent resource exhaustion:
```yaml
resources:
  limits:
    cpu: "500m"
    memory: "512Mi"
```

---

## What NOT to Do

❌ **Never commit these files to Git:**
- `~/.autoscaleops/config.enc`
- `~/.autoscaleops/.secrets`
- `~/.autoscaleops/.key`
- Any file containing API tokens

The `.gitignore` file already excludes these.

❌ **Never hard-code API keys** in Python files or YAML files.

❌ **Never share your instance ID** — it's tied to your encryption keys.

---

## Security Checklist

- ✅ API keys in Windows Credential Manager
- ✅ Config encrypted with AES-256
- ✅ Machine-specific encryption keys
- ✅ Non-root Docker containers
- ✅ Kubernetes namespace isolation
- ✅ Resource limits on all pods
- ✅ `.gitignore` excludes sensitive files
- ✅ Rotating log files (no infinite disk growth)