# TechNova Cloud — Troubleshooting Guide

## Deployment Stuck in "Pending" State
This usually means the cluster lacks available resources matching your requested CPU/memory. Try:
1. Reduce the requested replicas or resource requests in your deployment config.
2. Check Settings > Quota to confirm you haven't hit your plan's resource ceiling.
3. If on Free tier, upgrade to Pro for higher quota.

## Deployment Failing with "ImagePullBackOff"
This means TechNova Cloud cannot pull your container image. Common causes:
- The image tag doesn't exist or was deleted from your registry.
- Your registry requires authentication and you haven't configured registry credentials under Settings > Container Registries.
- The image platform (e.g. ARM vs x86) doesn't match the deployment's target architecture.

## API Returning 401 Unauthorized
- Confirm your API key hasn't been revoked (Settings > API Keys).
- Confirm you're sending the header as `Authorization: Bearer <key>`, not just the raw key.
- API keys expire after 1 year by default; check the "Expires" column.

## High Latency on API Requests
1. Check status.technova.cloud for any ongoing incidents in your region.
2. Latency commonly increases when nearing your plan's rate limit — review Usage dashboard.
3. Consider switching to a region closer to your primary user base.

## Webhook Not Firing
- Verify the webhook URL is publicly reachable (not localhost) and returns a 2xx response within 5 seconds.
- Check Settings > Webhooks > Delivery Logs for failed delivery attempts and error messages.
- Confirm your endpoint correctly verifies the HMAC signature — many failures are silent rejections from your own server.

## Login Issues / Account Locked
After 5 failed login attempts, accounts are locked for 15 minutes for security. Wait 15 minutes or use "Forgot Password" to reset and unlock immediately.

## Slow Dashboard Loading
Usually caused by browser extensions interfering with WebSocket connections used for real-time updates. Try an incognito window or disabling ad-blockers for *.technova.cloud.

## SSL Certificate Errors on Custom Domains
Custom domain SSL certificates are auto-provisioned via Let's Encrypt and can take up to 30 minutes after DNS propagation. Verify your CNAME record points to `ingress.technova.cloud`.
