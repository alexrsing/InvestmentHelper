from typing import Any, Dict, List

from services.gmail_service import GmailService


class Gmail:
    def __init__(self):
        self.gmail_service = GmailService()

    def get_all_risk_range_emails(self) -> List[Dict[str, Any]]:
        """
        Retrieve and process ALL RISK RANGE emails from history

        Returns:
            List of extracted risk range data from all emails
        """
        # Set max_emails to a very high number to get all emails
        # Gmail API typically caps at 500 per request, but the service will paginate
        return self.gmail_service.process_risk_range_emails(max_emails=500)

    def get_all_trend_range_emails(self) -> List[Dict[str, Any]]:
        """
        Retrieve and process ALL ETF Pro Plus trend range emails from history

        Returns:
            List of extracted trend range data from all emails
        """
        # Set max_emails to a very high number to get all emails
        return self.gmail_service.process_trend_range_emails(max_emails=500)

    def get_email_content(self, email_id: str) -> Dict[str, Any]:
        """
        Get the full content of a specific email

        Args:
            email_id: Gmail message ID

        Returns:
            Dictionary containing email content
        """
        return self.gmail_service.get_email_content(email_id)
