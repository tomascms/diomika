# GitHub Actions Secrets Setup

This document outlines all required GitHub Actions secrets for the CI/CD pipeline to function correctly.

## Required Secrets

### 1. Database Credentials
- **Name**: `DATABASE_URL`
- **Value**: PostgreSQL connection string
- **Format**: `postgresql://username:password@host:port/database`
- **Example**: `postgresql://diomika_user:strong_password@db.example.com:5432/diomika_prod`
- **Usage**: Database operations, migrations, E2E tests
- **Environment**: All (development, staging, production)

### 2. AWS Credentials
#### AWS Access Key ID
- **Name**: `AWS_ACCESS_KEY_ID`
- **Value**: IAM user access key
- **Permission**: S3 (GetObject, PutObject), CloudWatch Logs
- **Usage**: Invoice storage (S3), CloudWatch integration
- **Environment**: Production only (or staging for testing)

#### AWS Secret Access Key
- **Name**: `AWS_SECRET_ACCESS_KEY`
- **Value**: IAM user secret key (paired with access key above)
- **Permissions**: S3, CloudWatch
- **Usage**: Authorizes access key operations
- **Environment**: Production only

### 3. Slack Integration
- **Name**: `SLACK_WEBHOOK_URL`
- **Value**: Incoming webhook URL from Slack
- **Format**: `https://hooks.slack.com/services/{WORKSPACE_ID}/{CHANNEL_ID}/{TOKEN}`
- **Setup**:
  1. Go to Slack App Directory
  2. Search for "Incoming Webhooks"
  3. Create new webhook for your workspace
  4. Select target channel (e.g., #alerts)
  5. Copy webhook URL
- **Usage**: AlertManager notifications, deployment alerts
- **Scope**: organization level (available to all repos)
- **Environment**: Production

### 4. PagerDuty Integration
- **Name**: `PAGERDUTY_SERVICE_KEY`
- **Value**: PagerDuty integration key (Events API v2)
- **Setup**:
  1. Go to PagerDuty console
  2. Create new service or select existing
  3. Go to "Integrations" tab
  4. Add new "Events API v2" integration
  5. Copy the integration key
- **Usage**: Critical incident alerting, on-call escalation
- **Scope**: organization level
- **Environment**: Production only

### 5. GitGuardian API Key
- **Name**: `GITGUARDIAN_API_KEY`
- **Value**: API key from GitGuardian dashboard
- **Setup**:
  1. Log in to GitGuardian dashboard
  2. Go to Settings → API
  3. Create new API key with "secrets_read" scope
  4. Copy the key
- **Usage**: Secret detection in CI, pre-commit scanning
- **Scope**: organization level
- **Environment**: All (development, staging, production)

### 6. Container Registry Authentication
- **Name**: `REGISTRY_USERNAME`
- **Value**: Container registry username (GitHub, Docker Hub, or private registry)
- **Usage**: Push Docker images to registry
- **Note**: Can use `${{ github.actor }}` for GitHub Container Registry (GHCR)
- **Environment**: CI/CD only

- **Name**: `REGISTRY_PASSWORD`
- **Value**: Container registry token/password
- **Usage**: Authenticate to registry
- **Note**: For GHCR, use `${{ secrets.GITHUB_TOKEN }}` (built-in)
- **Environment**: CI/CD only

### 7. Email Service Credentials
- **Name**: `EMAIL_API_KEY`
- **Value**: API key from email service (SendGrid, Mailgun, etc.)
- **Usage**: Send transactional emails
- **Environment**: All (configuration varies by environment)

- **Name**: `EMAIL_FROM_ADDRESS`
- **Value**: Sender email address
- **Format**: `noreply@diomika.pt` or `orders@diomika.pt`
- **Usage**: Email source address
- **Environment**: All

### 8. Security Scanning Tools
- **Name**: `SONAR_TOKEN`
- **Value**: SonarQube token for code quality analysis
- **Setup**: SonarQube dashboard → User settings → Tokens
- **Usage**: Code quality metrics, security analysis
- **Environment**: CI/CD optional (recommended)

## How to Add Secrets

### Via GitHub Web Interface
1. Go to repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Enter Name and Value
4. Click "Add secret"

### Via GitHub CLI
```bash
gh secret set DATABASE_URL --body "postgresql://..."
gh secret set AWS_ACCESS_KEY_ID --body "AKIA..."
gh secret set AWS_SECRET_ACCESS_KEY --body "wJalrX..."
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/..."
gh secret set PAGERDUTY_SERVICE_KEY --body "P1234567890..."
gh secret set GITGUARDIAN_API_KEY --body "xxxxxxxxxxxx..."
```

### Via Organization Secrets (for multiple repos)
1. Go to GitHub Organization → Settings → Secrets and variables → Actions
2. Click "New organization secret"
3. Select which repositories can access it
4. Enter Name and Value

## Environment-Specific Secrets

### Development
- DATABASE_URL (dev database)
- Optional: AWS credentials (sandbox account)
- Optional: Slack webhook (dev channel)

### Staging
- DATABASE_URL (staging database)
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (staging bucket)
- SLACK_WEBHOOK_URL (staging channel)
- PAGERDUTY_SERVICE_KEY (staging integration)
- GITGUARDIAN_API_KEY

### Production
- DATABASE_URL (production database)
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (production bucket)
- SLACK_WEBHOOK_URL (production channel)
- PAGERDUTY_SERVICE_KEY (production integration)
- GITGUARDIAN_API_KEY
- EMAIL_API_KEY, EMAIL_FROM_ADDRESS

## Secret Rotation Schedule

| Secret | Rotation Frequency | Responsible Party |
|--------|-------------------|-------------------|
| AWS Credentials | Every 90 days | DevOps |
| Slack Webhook | On integration change | DevOps |
| PagerDuty Key | Every 180 days | DevOps/On-Call Lead |
| GitGuardian API Key | Every 180 days | Security Team |
| Database Password | Every 90 days | DBA/DevOps |
| Email API Key | Every 90 days | DevOps |

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use environment-specific secrets** - don't expose production secrets to development CI
3. **Rotate secrets regularly** - set calendar reminders
4. **Use least privilege** - grant minimum required permissions
5. **Monitor secret usage** - check GitHub audit logs
6. **Use short-lived tokens** when possible
7. **Disable unused credentials** immediately
8. **Document secret changes** in a private log

## Verification Checklist

After setting up all secrets, run:

```bash
# List all secrets (without values)
gh secret list

# Verify specific secret exists (does not show value)
gh secret list | grep DATABASE_URL
```

## Troubleshooting

### Secret Not Found in Workflow
- Verify exact spelling (case-sensitive: `DATABASE_URL` ≠ `database_url`)
- Check secret is set at correct level (repo vs. organization)
- Confirm workflow file uses: `${{ secrets.SECRET_NAME }}`
- Ensure workflow file is on a branch with access to secrets

### Authentication Failures in CI
- Verify secret value has not changed in source system
- Check secret rotation date - may need renewal
- Confirm IAM/API permissions are still active
- Review CI/CD logs for detailed error messages

### AWS S3 Errors
- Verify bucket name matches in code and secret
- Check IAM policy includes s3:GetObject and s3:PutObject
- Confirm bucket exists in correct region
- Validate CORS configuration if cross-origin access needed

### Slack/PagerDuty Not Receiving Alerts
- Verify webhook URL is valid (test with curl)
- Check channel/service still exists
- Review integration permissions
- Confirm JSON payload format matches expected schema

## Related Documentation
- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)
- [PagerDuty Events API](https://developer.pagerduty.com/docs/events-api-v2/overview/)
