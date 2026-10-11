"""Best-effort Twilio notifications for passkey-verified emergency access."""

import logging
import re
from datetime import datetime, timezone
from html import escape

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_emergency_contact_alert(
    *,
    phone: str,
    patient_name: str,
    doctor_name: str,
    organization: str | None,
    accessed_at: str,
) -> None:
    """Place a trial-compatible voice alert; never interrupt emergency access."""
    settings = get_settings()
    if not settings.twilio_configured:
        logger.warning(
            "Emergency contact notification skipped; missing Twilio settings: %s",
            ", ".join(settings.twilio_missing_settings),
        )
        return

    place = organization.strip() if organization and organization.strip() else "an organization not listed in CareKey"
    text = (
        f"CareKey alert: {patient_name}'s emergency profile was accessed by {doctor_name} at {place} "
        f"on {accessed_at}. This is an access notification; no medical details are included."
    )
    twiml = f"<Response><Say>{escape(text)}</Say></Response>"
    base_url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}"
    auth = (settings.twilio_account_sid, settings.twilio_auth_token)
    try:
        with httpx.Client(timeout=8.0, auth=auth) as client:
            response = client.post(
                f"{base_url}/Calls.json",
                data={"To": phone, "Twiml": twiml},
            )
            response.raise_for_status()
            logger.info("Emergency contact custom voice call accepted by Twilio")
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Emergency contact voice call rejected by Twilio (HTTP %s, error code %s): %s",
            exc.response.status_code,
            _twilio_error_code(exc.response),
            _twilio_error_message(exc.response, (phone, settings.twilio_from_number or "")),
        )
    except Exception as exc:
        logger.warning("Emergency contact voice request failed (%s)", type(exc).__name__)


def _twilio_error_code(response: httpx.Response) -> str:
    try:
        code = response.json().get("code")
    except (ValueError, AttributeError):
        code = None
    return str(code) if code is not None else "unknown"


def _twilio_error_message(response: httpx.Response, sensitive_values: tuple[str, ...]) -> str:
    try:
        message = response.json().get("message")
    except (ValueError, AttributeError):
        message = None
    if not isinstance(message, str) or not message.strip():
        return "No error message returned"

    for value in sorted((item for item in sensitive_values if item), key=len, reverse=True):
        message = message.replace(value, "[redacted]")
    message = re.sub(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)", "[number redacted]", message)
    return message[:400]


def emergency_access_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
