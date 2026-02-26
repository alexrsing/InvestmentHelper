"""
Secure logging utilities for Hedgeye Risk Ranges Tracker.

This module provides functions to safely log sensitive information
by redacting or masking credentials and other sensitive data.
"""

import re
from typing import Any, Dict, Optional

# Patterns for sensitive data that should be redacted
SENSITIVE_PATTERNS = [
    (r'(private_key["\']?\s*[=:]\s*["\']?)([^"\']+)', r"\1[REDACTED]"),
    (r'(password["\']?\s*[=:]\s*["\']?)([^"\']+)', r"\1[REDACTED]"),
    (r'(secret["\']?\s*[=:]\s*["\']?)([^"\']+)', r"\1[REDACTED]"),
    (r'(token["\']?\s*[=:]\s*["\']?)([^"\']+)', r"\1[REDACTED]"),
    (r'(api_key["\']?\s*[=:]\s*["\']?)([^"\']+)', r"\1[REDACTED]"),
    (r"(AWS_SECRET_ACCESS_KEY[=:]\s*)([^\s]+)", r"\1[REDACTED]"),
    (r"(AWS_ACCESS_KEY_ID[=:]\s*)([^\s]+)", r"\1[REDACTED]"),
]

# Email patterns to mask (show first few chars + domain)
EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")


def mask_email(email: str) -> str:
    """
    Mask an email address, showing only first 2 chars and domain.

    Args:
        email: Email address to mask

    Returns:
        Masked email like "sh***@singtech.com.au"
    """
    match = EMAIL_PATTERN.match(email)
    if match:
        local, domain = match.groups()
        if len(local) <= 2:
            masked_local = local[0] + "***"
        else:
            masked_local = local[:2] + "***"
        return f"{masked_local}@{domain}"
    return email


def mask_string(value: str, visible_chars: int = 4) -> str:
    """
    Mask a string, showing only first N characters.

    Args:
        value: String to mask
        visible_chars: Number of characters to show (default 4)

    Returns:
        Masked string like "AKIA***"
    """
    if not value or len(value) <= visible_chars:
        return "***"
    return value[:visible_chars] + "***"


def mask_service_account_email(email: str) -> str:
    """
    Mask a Google service account email.
    Shows the service name portion but masks the unique ID.

    Args:
        email: Service account email like "hedgeye-service@project-123456.iam.gserviceaccount.com"

    Returns:
        Masked email like "hedgeye-service@***.iam.gserviceaccount.com"
    """
    if not email:
        return "***"

    # Service account emails have format: name@project-id.iam.gserviceaccount.com
    parts = email.split("@")
    if len(parts) == 2:
        name = parts[0]
        domain = parts[1]

        # Mask the project ID in the domain
        domain_parts = domain.split(".")
        if len(domain_parts) >= 3 and "gserviceaccount" in domain:
            # Format: project-id.iam.gserviceaccount.com
            masked_domain = "***.iam.gserviceaccount.com"
            return f"{name}@{masked_domain}"

    return mask_email(email)


def redact_sensitive_data(message: str) -> str:
    """
    Redact sensitive data patterns from a message.

    Args:
        message: Message that may contain sensitive data

    Returns:
        Message with sensitive data redacted
    """
    result = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def safe_dict_repr(data: Dict[str, Any], sensitive_keys: Optional[set] = None) -> str:
    """
    Create a safe string representation of a dictionary,
    redacting values for sensitive keys.

    Args:
        data: Dictionary to represent
        sensitive_keys: Set of keys whose values should be redacted.
                       If None, uses default sensitive keys.

    Returns:
        Safe string representation
    """
    if sensitive_keys is None:
        sensitive_keys = {
            "private_key",
            "private_key_id",
            "client_secret",
            "password",
            "secret",
            "token",
            "api_key",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_ACCESS_KEY_ID",
        }

    safe_data = {}
    for key, value in data.items():
        if key in sensitive_keys:
            safe_data[key] = "[REDACTED]"
        elif key == "client_email":
            safe_data[key] = mask_service_account_email(str(value)) if value else "[NOT SET]"
        elif isinstance(value, dict):
            safe_data[key] = safe_dict_repr(value, sensitive_keys)
        elif isinstance(value, str) and len(value) > 100:
            # Long strings are likely sensitive (e.g., private keys)
            safe_data[key] = f"[{len(value)} chars]"
        else:
            safe_data[key] = value

    return str(safe_data)


def log_credential_source(source: str, success: bool = True) -> str:
    """
    Generate a log message for credential loading.

    Args:
        source: Description of where credentials were loaded from
        success: Whether loading was successful

    Returns:
        Safe log message
    """
    status = "Successfully loaded" if success else "Failed to load"
    return f"{status} credentials from {source}"


def log_authentication_result(service: str, success: bool, identity_hint: Optional[str] = None) -> str:
    """
    Generate a safe log message for authentication results.

    Args:
        service: Name of the service (e.g., "Gmail", "AWS")
        success: Whether authentication succeeded
        identity_hint: Optional masked hint about the identity used

    Returns:
        Safe log message
    """
    status = "succeeded" if success else "failed"
    message = f"{service} authentication {status}"

    if identity_hint and success:
        message += f" (identity: {identity_hint})"

    return message
