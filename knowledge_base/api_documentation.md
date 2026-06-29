# TechNova Cloud — API Documentation

## Authentication
All API requests require a Bearer token in the Authorization header:
`Authorization: Bearer <YOUR_API_KEY>`
API keys can be generated from Settings > API Keys. Each key can be scoped to read-only or read-write permissions.

## Base URL
All endpoints are relative to `https://api.technova.cloud/v1`.

## Rate Limits
- Free plan: 60 requests/minute
- Pro plan: 600 requests/minute
- Business plan: 3000 requests/minute
- Enterprise plan: custom limits negotiated per contract

Exceeding the limit returns HTTP 429 with a `Retry-After` header indicating seconds to wait.

## Common Endpoints

### GET /deployments
Returns a list of all deployments in the current workspace. Supports pagination via `?page=` and `?limit=` query parameters.

### POST /deployments
Creates a new deployment. Requires `name`, `image`, `region`, and `replicas` in the request body.

### GET /deployments/{id}/logs
Streams the last 1000 log lines for a given deployment. Supports `?since=<timestamp>` for incremental fetching.

### DELETE /deployments/{id}
Deletes a deployment. This is irreversible. Requires read-write API key scope.

### GET /usage
Returns current billing-period usage metrics: compute hours, bandwidth, and storage.

## Error Codes
- 400: Malformed request body
- 401: Invalid or missing API key
- 403: API key lacks required scope
- 404: Resource not found
- 429: Rate limit exceeded
- 500: Internal server error — if this persists, contact support with the `x-request-id` header value

## Webhooks
You can configure webhooks under Settings > Webhooks to receive POST notifications for events like `deployment.succeeded`, `deployment.failed`, and `usage.threshold_reached`. Webhook payloads are signed with HMAC-SHA256; verify using the secret shown when you create the webhook.

## SDKs
Official SDKs are available for Python (`pip install technova-sdk`), Node.js (`npm install @technova/sdk`), and Go (`go get github.com/technova/sdk-go`).
