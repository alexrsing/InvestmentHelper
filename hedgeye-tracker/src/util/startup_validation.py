"""
Startup validation module for Hedgeye Risk Ranges Tracker.

This module validates all required credentials and configuration before
the application begins processing data. It fails fast with clear error
messages if any validation fails.
"""

import json
import os
import re
import sys
from typing import List, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError


class ValidationError(Exception):
    """Raised when startup validation fails."""

    pass


class StartupValidator:
    """Validates application configuration and credentials on startup."""

    # Placeholder values that indicate unconfigured settings
    PLACEHOLDER_VALUES = {
        "your-email@example.com",
        "your-email@domain.com",
        "example-key",
        "your-access-key",
        "your-secret-key",
        "placeholder",
        "changeme",
        "xxx",
        "YOUR_",
    }

    # Valid AWS regions
    VALID_AWS_REGIONS = {
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
        "ap-south-1",
        "ap-northeast-1",
        "ap-northeast-2",
        "ap-northeast-3",
        "ap-southeast-1",
        "ap-southeast-2",
        "ca-central-1",
        "eu-central-1",
        "eu-west-1",
        "eu-west-2",
        "eu-west-3",
        "eu-north-1",
        "sa-east-1",
    }

    def __init__(self, skip_connectivity: bool = False):
        """
        Initialize the validator.

        Args:
            skip_connectivity: If True, skip AWS and Gmail connectivity checks.
                             Useful for testing or offline validation.
        """
        self.skip_connectivity = skip_connectivity
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Run all validation checks.

        Returns:
            Tuple of (success, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Validate environment variables
        self._validate_aws_region()
        self._validate_gmail_config()

        # Validate connectivity (unless skipped)
        if not self.skip_connectivity:
            self._validate_aws_connectivity()
            self._validate_gmail_connectivity()

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_aws_region(self) -> None:
        """Validate AWS_REGION or AWS_REGION_NAME is set and valid."""
        # AWS_REGION is set by Lambda automatically, AWS_REGION_NAME is our custom var
        region = (os.getenv("AWS_REGION") or os.getenv("AWS_REGION_NAME", "")).strip()

        if not region:
            self.errors.append(
                "AWS_REGION or AWS_REGION_NAME environment variable is not set. "
                "Set it to a valid AWS region (e.g., us-west-2)."
            )
            return

        if region not in self.VALID_AWS_REGIONS:
            self.warnings.append(
                f"AWS region '{region}' may not be a standard region. "
                f"Common regions: us-east-1, us-west-2, eu-west-1."
            )

    def _validate_gmail_config(self) -> None:
        """Validate Gmail configuration."""
        user_email = os.getenv("GMAIL_USER_EMAIL", "").strip()
        secret_name = os.getenv("GMAIL_SECRET_NAME", "").strip()

        # Check GMAIL_USER_EMAIL
        if not user_email:
            self.errors.append(
                "GMAIL_USER_EMAIL environment variable is not set. "
                "Set it to the Gmail address to impersonate (e.g., user@company.com)."
            )
        elif self._is_placeholder(user_email):
            self.errors.append(
                f"GMAIL_USER_EMAIL appears to be a placeholder value: '{user_email}'. "
                "Set it to the actual Gmail address to impersonate."
            )
        elif not self._is_valid_email(user_email):
            self.errors.append(f"GMAIL_USER_EMAIL '{user_email}' does not appear to be a valid email address.")

        # Check GMAIL_SECRET_NAME
        if not secret_name:
            self.errors.append(
                "GMAIL_SECRET_NAME environment variable is not set. "
                "Set it to the AWS Secrets Manager secret name containing Gmail credentials."
            )
        elif self._is_placeholder(secret_name):
            self.errors.append(
                f"GMAIL_SECRET_NAME appears to be a placeholder value: '{secret_name}'. "
                "Set it to the actual Secrets Manager secret name."
            )

        # Check for deprecated GMAIL_APP_DETAILS
        if os.getenv("GMAIL_APP_DETAILS"):
            self.warnings.append(
                "GMAIL_APP_DETAILS is deprecated. "
                "Migrate to AWS Secrets Manager by setting GMAIL_SECRET_NAME instead."
            )

    def _validate_aws_connectivity(self) -> None:
        """Validate AWS connectivity by checking we can make AWS API calls."""
        region = os.getenv("AWS_REGION") or os.getenv("AWS_REGION_NAME", "us-east-1")

        try:
            # Create STS client and verify credentials are valid
            sts = boto3.client("sts", region_name=region)
            identity = sts.get_caller_identity()

            # Log the identity for debugging
            account = identity.get("Account", "unknown")
            arn = identity.get("Arn", "unknown")
            print(f"  AWS Identity: {arn} (Account: {account})")

        except NoCredentialsError:
            self.errors.append(
                "AWS credentials not found. Configure credentials using one of:\n"
                "  1. IAM role (recommended for EC2/Lambda)\n"
                "  2. AWS CLI: aws configure\n"
                "  3. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            self.errors.append(f"AWS authentication failed: {error_code} - {e}")
        except BotoCoreError as e:
            self.errors.append(f"AWS connectivity error: {e}")

    def _validate_gmail_connectivity(self) -> None:
        """Validate Gmail credentials can be retrieved from Secrets Manager."""
        secret_name = os.getenv("GMAIL_SECRET_NAME", "")
        region = os.getenv("AWS_REGION") or os.getenv("AWS_REGION_NAME", "us-east-1")

        if not secret_name:
            # Already reported in config validation
            return

        try:
            # Create Secrets Manager client
            session = boto3.session.Session()
            client = session.client(service_name="secretsmanager", region_name=region)

            # Try to retrieve the secret
            response = client.get_secret_value(SecretId=secret_name)
            secret_string = response.get("SecretString", "")

            # Validate it's valid JSON
            try:
                credentials = json.loads(secret_string)
            except json.JSONDecodeError:
                self.errors.append(
                    f"Gmail secret '{secret_name}' does not contain valid JSON. "
                    "Ensure the secret contains the service account credentials JSON."
                )
                return

            # Validate required fields for service account
            required_fields = ["type", "project_id", "private_key", "client_email"]
            missing_fields = [f for f in required_fields if f not in credentials]

            if missing_fields:
                self.errors.append(
                    f"Gmail credentials are missing required fields: {', '.join(missing_fields)}. "
                    "Ensure the secret contains a valid Google service account JSON."
                )
            elif credentials.get("type") != "service_account":
                self.warnings.append(
                    f"Gmail credentials type is '{credentials.get('type')}', expected 'service_account'. "
                    "Ensure you're using a service account, not OAuth credentials."
                )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ResourceNotFoundException":
                self.errors.append(
                    f"Gmail secret '{secret_name}' not found in Secrets Manager. "
                    f"Create it using: aws secretsmanager put-secret-value "
                    f"--secret-id {secret_name} --secret-string file://credentials.json"
                )
            elif error_code == "AccessDeniedException":
                self.errors.append(
                    f"Access denied to Gmail secret '{secret_name}'. "
                    "Ensure IAM role/user has secretsmanager:GetSecretValue permission."
                )
            else:
                self.errors.append(f"Failed to retrieve Gmail secret: {error_code} - {e}")
        except Exception as e:
            self.errors.append(f"Unexpected error validating Gmail credentials: {e}")

    def _is_placeholder(self, value: str) -> bool:
        """Check if a value appears to be a placeholder."""
        value_lower = value.lower()
        for placeholder in self.PLACEHOLDER_VALUES:
            if placeholder.lower() in value_lower:
                return True
        return False

    def _is_valid_email(self, email: str) -> bool:
        """Basic email format validation."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))


def validate_startup(skip_connectivity: bool = False) -> None:
    """
    Validate application startup configuration.

    Exits with non-zero code if validation fails.

    Args:
        skip_connectivity: If True, skip AWS and Gmail connectivity checks.
    """
    print("=" * 60)
    print("STARTUP VALIDATION")
    print("=" * 60)

    validator = StartupValidator(skip_connectivity=skip_connectivity)
    success, errors, warnings = validator.validate_all()

    # Print warnings
    if warnings:
        print()
        print("WARNINGS:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")

    # Print errors
    if errors:
        print()
        print("ERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        print()
        print("=" * 60)
        print("VALIDATION FAILED - Please fix the above errors and retry.")
        print("=" * 60)
        sys.exit(1)

    print()
    print("✅ All startup validations passed")
    print("=" * 60)
    print()


if __name__ == "__main__":
    # Allow running validation standalone
    import argparse

    parser = argparse.ArgumentParser(description="Validate application startup configuration")
    parser.add_argument("--skip-connectivity", action="store_true", help="Skip AWS and Gmail connectivity checks")
    args = parser.parse_args()

    # Load environment variables
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    load_dotenv(env_path)

    validate_startup(skip_connectivity=args.skip_connectivity)
