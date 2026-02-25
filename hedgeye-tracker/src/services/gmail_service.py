"""Creates a Gmail API client to be able to read emails from Hedgeye."""

import base64
import json
import os
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from services.risk_range_parser_service import RiskRangeParserService
from services.trend_range_parser_service import TrendRangeParserService
from util.secure_logging import mask_email, mask_service_account_email


class GmailService:
    def __init__(self):
        self.user_email = os.getenv("GMAIL_USER_EMAIL", "")  # Gmail account to impersonate
        self.client = None
        self.authenticate()

    def _get_credentials_from_secrets_manager(self) -> Dict[str, Any]:
        """
        Retrieve Gmail service account credentials from AWS Secrets Manager.

        Returns:
            Dictionary containing service account credentials

        Raises:
            Exception: If secret cannot be retrieved or parsed
        """
        secret_name = os.getenv("GMAIL_SECRET_NAME", "dev/hedgeye/gmail-service-account")
        region_name = os.getenv("AWS_REGION") or os.getenv("AWS_REGION_NAME", "us-west-2")

        # Create a Secrets Manager client
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=region_name)

        try:
            print(f"Fetching secret from Secrets Manager: {secret_name}")
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)

            # Parse the secret string as JSON
            secret_string = get_secret_value_response["SecretString"]
            credentials_info = json.loads(secret_string)

            print("✅ Successfully retrieved credentials from Secrets Manager")
            return credentials_info

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                raise Exception(
                    f"Secret '{secret_name}' not found in Secrets Manager. "
                    f"Please create the secret using: "
                    f"aws secretsmanager put-secret-value --secret-id {secret_name} "
                    f"--secret-string file://service-account.json"
                )
            elif error_code == "InvalidRequestException":
                raise Exception(f"Invalid request to Secrets Manager: {e}")
            elif error_code == "InvalidParameterException":
                raise Exception(f"Invalid parameter in Secrets Manager request: {e}")
            elif error_code == "DecryptionFailure":
                raise Exception(f"Failed to decrypt secret: {e}")
            elif error_code == "InternalServiceError":
                raise Exception(f"Secrets Manager internal service error: {e}")
            else:
                raise Exception(f"Error retrieving secret from Secrets Manager: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Secret value is not valid JSON: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error retrieving credentials: {e}")

    def authenticate(self):
        """Authenticates using Service Account for server-to-server access."""
        # Use the working scope from delegation test
        SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

        try:
            # Try to get credentials from Secrets Manager first, then fall back to environment variable
            credentials_info = None

            # Try Secrets Manager first (preferred method)
            try:
                credentials_info = self._get_credentials_from_secrets_manager()
                print("✅ Loaded credentials from AWS Secrets Manager")
            except Exception as secrets_error:
                print(f"⚠️ Could not load from Secrets Manager: {secrets_error}")

                # Fall back to environment variable (legacy method)
                gmail_app_details = os.getenv("GMAIL_APP_DETAILS")
                if gmail_app_details:
                    print("⚠️ Falling back to GMAIL_APP_DETAILS environment variable (DEPRECATED)")
                    try:
                        credentials_info = json.loads(gmail_app_details)
                        print("✅ Loaded credentials from environment variable")
                    except json.JSONDecodeError as e:
                        raise Exception(f"Invalid JSON in GMAIL_APP_DETAILS environment variable: {e}")
                else:
                    raise Exception(
                        "Neither AWS Secrets Manager nor GMAIL_APP_DETAILS environment variable found. "
                        "Please configure GMAIL_SECRET_NAME to use Secrets Manager."
                    )

            # Create service account credentials
            credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)

            # If user_email is provided, delegate to that user (domain-wide delegation)
            if self.user_email:
                masked_user = mask_email(self.user_email)
                print(f"Using domain-wide delegation to impersonate: {masked_user}")
                credentials = credentials.with_subject(self.user_email)
            else:
                print("No user email specified - using service account directly")

            # Log service account identity (masked for security)
            client_email = credentials_info.get("client_email", "")
            masked_sa_email = mask_service_account_email(client_email)
            print(f"Service account: {masked_sa_email}")
            print(f"Using scopes: {SCOPES}")

            # Test credential refresh
            print("Testing credential refresh...")
            try:
                credentials.refresh(Request())
                print("✅ Credential refresh successful!")
            except Exception as refresh_error:
                print(f"❌ Credential refresh failed: {refresh_error}")
                raise

            # Build Gmail service
            service = build("gmail", "v1", credentials=credentials)
            self.client = service
            return service

        except Exception as error:
            print(f"Authentication error: {error}")
            raise

    def get_email_id(self, subject_filter: str) -> str:
        """Get email ID matching the subject filter."""
        if self.client is None:
            self.authenticate()

        if self.client is None:
            raise Exception("Failed to authenticate Gmail client")

        try:
            # Search for emails with the subject filter
            email = self.client.users().messages().list(userId="me", q=f'subject:"{subject_filter}"').execute()

            if "messages" not in email or not email["messages"]:
                raise Exception(f"No emails found with subject containing: {subject_filter}")

            # Get the latest email matching the filter
            email_id = email["messages"][0]["id"]
            return email_id

        except HttpError as error:
            print(f"Error fetching email: {error}")
            raise

    def get_emails_by_subject(self, subject_keywords: List[str], max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get emails containing any of the specified subject keywords

        Args:
            subject_keywords: List of keywords to search for in email subjects
            max_results: Maximum number of emails to return

        Returns:
            List of email dictionaries with id, subject, and sender info
        """
        if self.client is None:
            self.authenticate()

        if self.client is None:
            raise Exception("Failed to authenticate Gmail client")

        try:
            found_emails = []

            for keyword in subject_keywords:
                print(f"Searching for emails with subject containing: {keyword}")

                # Search for emails with the subject keyword
                result = (
                    self.client.users()
                    .messages()
                    .list(userId="me", q=f'subject:"{keyword}"', maxResults=max_results)
                    .execute()
                )

                if "messages" in result:
                    for message in result["messages"]:
                        # Get message details
                        msg = (
                            self.client.users()
                            .messages()
                            .get(
                                userId="me",
                                id=message["id"],
                                format="metadata",
                                metadataHeaders=["Subject", "From", "Date"],
                            )
                            .execute()
                        )

                        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

                        email_info = {
                            "id": message["id"],
                            "subject": headers.get("Subject", ""),
                            "from": headers.get("From", ""),
                            "date": headers.get("Date", ""),
                            "keyword_matched": keyword,
                        }

                        # Avoid duplicates
                        if not any(email["id"] == email_info["id"] for email in found_emails):
                            found_emails.append(email_info)

            print(f"Found {len(found_emails)} unique emails")
            return found_emails

        except HttpError as error:
            print(f"Error searching emails: {error}")
            raise

    def get_email_content(self, email_id: str) -> Dict[str, Any]:
        """
        Get the full content of an email including HTML body and attachments

        Args:
            email_id: Gmail message ID

        Returns:
            Dictionary containing email content, HTML body, and attachments
        """
        if self.client is None:
            self.authenticate()

        if self.client is None:
            raise Exception("Failed to authenticate Gmail client")

        try:
            message = self.client.users().messages().get(userId="me", id=email_id).execute()

            # Extract headers
            headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}

            # Extract email content
            email_content = {
                "id": email_id,
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "date": headers.get("Date", ""),
                "html_body": "",
                "text_body": "",
                "attachments": [],
            }

            # Extract body content
            self._extract_message_parts(message["payload"], email_content)

            return email_content

        except HttpError as error:
            print(f"Error fetching email content: {error}")
            raise

    def _extract_message_parts(self, payload: Dict[str, Any], email_content: Dict[str, Any]):
        """
        Recursively extract message parts (HTML, text, attachments)
        """
        try:
            # Handle single part message
            if "parts" not in payload:
                self._process_message_part(payload, email_content)
                return

            # Handle multipart message
            for part in payload.get("parts", []):
                self._extract_message_parts(part, email_content)

        except Exception as e:
            print(f"Error extracting message parts: {e}")

    def _process_message_part(self, part: Dict[str, Any], email_content: Dict[str, Any]):
        """
        Process a single message part
        """
        try:
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")

            # Handle attachments
            if filename:
                attachment_id = part["body"].get("attachmentId")
                if attachment_id:
                    attachment = (
                        self.client.users()
                        .messages()
                        .attachments()
                        .get(userId="me", messageId=email_content["id"], id=attachment_id)
                        .execute()
                    )

                    attachment_data = base64.urlsafe_b64decode(attachment.get("data", ""))

                    email_content["attachments"].append(
                        {
                            "filename": filename,
                            "mime_type": mime_type,
                            "data": attachment_data,
                            "size": len(attachment_data),
                        }
                    )
                return

            # Handle body content
            body_data = part["body"].get("data", "")
            if body_data:
                decoded_data = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")

                if mime_type == "text/html":
                    email_content["html_body"] += decoded_data
                elif mime_type == "text/plain":
                    email_content["text_body"] += decoded_data

        except Exception as e:
            print(f"Error processing message part: {e}")

    def process_risk_range_emails(self, max_emails: int = 5) -> List[Dict[str, Any]]:
        """
        Find and process RISK RANGE™ SIGNALS emails

        Args:
            max_emails: Maximum number of emails to process

        Returns:
            List of extracted risk range data
        """
        try:
            # Search for risk range emails
            risk_range_keywords = ["RISK RANGE™ SIGNALS", "RISK RANGE SIGNALS", "RISK RANGE"]

            emails = self.get_emails_by_subject(risk_range_keywords, max_emails)

            if not emails:
                print("No RISK RANGE emails found")
                return []

            parser = RiskRangeParserService()
            all_risk_ranges = []

            for email_info in emails:
                print(f"Processing email: {email_info['subject'][:50]}...")

                email_content = self.get_email_content(email_info["id"])

                if email_content["html_body"]:
                    risk_ranges = parser.extract_risk_ranges_from_html(email_content["html_body"])
                    validated_ranges = parser.validate_extracted_data(risk_ranges)

                    for range_data in validated_ranges:
                        range_data["email_id"] = email_info["id"]
                        range_data["email_subject"] = email_info["subject"]
                        range_data["email_date"] = email_info["date"]

                    all_risk_ranges.extend(validated_ranges)
                    print(f"Extracted {len(validated_ranges)} risk ranges from this email")
                else:
                    print("No HTML content found in email")

            print(f"Total risk ranges extracted: {len(all_risk_ranges)}")
            return all_risk_ranges

        except Exception as e:
            print(f"Error processing risk range emails: {e}")
            return []

    def process_trend_range_emails(self, max_emails: int = 5) -> List[Dict[str, Any]]:
        """
        Find and process ETF Pro Plus trend range emails

        Args:
            max_emails: Maximum number of emails to process

        Returns:
            List of extracted trend range data
        """
        try:
            # Search for ETF Pro Plus emails
            trend_range_keywords = ["ETF Pro Plus", "ETF Pro Plus - Levels", "ETF Pro Plus - New Weekly Report"]

            emails = self.get_emails_by_subject(trend_range_keywords, max_emails)

            if not emails:
                print("No ETF Pro Plus emails found")
                return []

            parser = TrendRangeParserService()
            all_trend_ranges = []

            for email_info in emails:
                print(f"Processing email: {email_info['subject'][:50]}...")

                email_content = self.get_email_content(email_info["id"])

                if email_content["html_body"]:
                    trend_ranges = parser.extract_trend_ranges_from_html(email_content["html_body"])
                    validated_ranges = parser.validate_extracted_data(trend_ranges)

                    for range_data in validated_ranges:
                        range_data["email_id"] = email_info["id"]
                        range_data["email_subject"] = email_info["subject"]
                        range_data["email_date"] = email_info["date"]

                    all_trend_ranges.extend(validated_ranges)
                    print(f"Extracted {len(validated_ranges)} trend ranges from this email")
                else:
                    print("No HTML content found in email")

            print(f"Total trend ranges extracted: {len(all_trend_ranges)}")
            return all_trend_ranges

        except Exception as e:
            print(f"Error processing trend range emails: {e}")
            return []

    def get_all_email_attachments(self, email_id: str) -> bytes:
        """Gets all attachments from an email."""
        if self.client is None:
            self.authenticate()

        if self.client is None:
            raise Exception("Failed to authenticate Gmail client")

        try:
            message = self.client.users().messages().get(userId="me", id=email_id).execute()
            attachment_data = b""

            # Handle single part messages
            if "parts" not in message["payload"]:
                return attachment_data

            for part in message["payload"].get("parts", []):
                if part.get("filename"):
                    attachment_id = part["body"].get("attachmentId")
                    if attachment_id:
                        attachment = (
                            self.client.users()
                            .messages()
                            .attachments()
                            .get(userId="me", messageId=email_id, id=attachment_id)
                            .execute()
                        )

                        # Decode base64 attachment data
                        attachment_data += base64.urlsafe_b64decode(attachment.get("data", ""))

            return attachment_data

        except HttpError as error:
            print(f"Error fetching email attachments: {error}")
            raise


# Tests
if __name__ == "__main__":
    # Load environment variables from .env file
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # Add parent directory to path
    from util.env_loader import load_env_file

    # Load .env file from project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    load_env_file(env_path)

    gmail_service = GmailService()

    print("🔍 Testing email search functionality...")

    # Test different search terms
    search_terms = [
        "RISK RANGE™ SIGNALS:",  # Without trademark symbol
        "RISK RANGE SIGNALS:",  # With trademark symbol
        "RISK RANGE",  # Just the main part
        "ETF Pro Plus - Levels",  # Alternative emails
        "subject:RISK",  # Broader search
    ]

    for term in search_terms:
        print(f"\n📧 Searching for: '{term}'")
        try:
            if gmail_service.client is None:
                print("  ❌ Gmail client not authenticated")
                continue

            # Try a broader search first
            results = gmail_service.client.users().messages().list(userId="me", q=term, maxResults=2).execute()

            if "messages" in results and results["messages"]:
                print(f"  ✅ Found {len(results['messages'])} email(s)")

                # Get the subject of the first email to see actual format
                first_email = (
                    gmail_service.client.users()
                    .messages()
                    .get(
                        userId="me",
                        id=results["messages"][0]["id"],
                        format="metadata",
                        metadataHeaders=["Subject", "From", "Date"],
                    )
                    .execute()
                )

                headers = {h["name"]: h["value"] for h in first_email["payload"]["headers"]}
                print(f"  📋 Sample subject: '{headers.get('Subject', 'No subject')}'")
                print(f"  📨 From: {headers.get('From', 'Unknown')}")
                print(f"  📅 Date: {headers.get('Date', 'Unknown')}")
                break
            else:
                print("  ❌ No emails found")
        except Exception as e:
            print(f"  ⚠️ Search error: {e}")

    print("\n🔍 Listing recent emails to see what's available...")
    try:
        if gmail_service.client is None:
            print("❌ Gmail client not authenticated, cannot list emails")
        else:
            recent = gmail_service.client.users().messages().list(userId="me", maxResults=2).execute()

            if "messages" in recent:
                print("Recent emails in mailbox:")
                for i, msg in enumerate(recent["messages"][:5]):
                    email = (
                        gmail_service.client.users()
                        .messages()
                        .get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["Subject", "From"])
                        .execute()
                    )

                    headers = {h["name"]: h["value"] for h in email["payload"]["headers"]}
                    subject = headers.get("Subject", "No subject")[:60]
                    sender = headers.get("From", "Unknown")[:30]
                    print(f"  {i+1}. {subject}... (from: {sender})")

    except Exception as e:
        print(f"Error listing recent emails: {e}")
