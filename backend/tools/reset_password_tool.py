"""
Tool: reset_password

Simulates triggering a password reset email, the way it would work against
a real identity/auth service (e.g. Auth0, Cognito, or an internal user
service). Since this is a portfolio/demo project with no real user
database or email server, we simulate the action deterministically and
log it, rather than connecting to a real mail provider.

In a real production system, this function would call out to an internal
"identity-service" API instead of generating a token locally.
"""

import secrets
from datetime import datetime, timedelta

from pydantic import BaseModel, EmailStr

from backend.utils.logger import logger


class ResetPasswordInput(BaseModel):
    email: EmailStr


def reset_password(email: str) -> dict:
    """
    Simulates sending a password reset link to `email`. Generates a
    short-lived, single-use-looking token and an expiry timestamp, matching
    the behavior described in the FAQ ("reset link valid for 30 minutes").

    Returns a dict describing the action taken, which the agent relays to
    the customer (without exposing the raw token in a real system — here
    we include it only because there's no real email channel to send it
    through).
    """
    logger.info("Tool called: reset_password(email='{}')", email)

    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    # In production: enqueue a transactional email via SendGrid/SES here,
    # and never return the raw token to the caller.
    return {
        "email": email,
        "reset_link": f"https://app.technova.cloud/reset-password?token={token}",
        "expires_at": expires_at.isoformat(),
        "message": (
            f"A password reset link has been sent to {email}. "
            "It will expire in 30 minutes."
        ),
    }
