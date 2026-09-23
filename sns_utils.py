"""
SNS Utility Module for Campus Gate Pass System.
Handles publishing alerts to Admin when a new gate pass request is submitted.
"""

import os
import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")


def get_sns_client():
    """Initializes and returns a boto3 SNS client."""
    kwargs = {"region_name": AWS_REGION}
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if aws_access_key and aws_secret_key:
        kwargs["aws_access_key_id"] = aws_access_key
        kwargs["aws_secret_access_key"] = aws_secret_key
    return boto3.client("sns", **kwargs)


def notify_admin_new_request(pass_id: int, name: str, reason: str, out_time: str, return_time: str, email: str) -> dict:
    """
    Publishes an SNS alert to the Admin when a student submits a new gate pass request.
    """
    topic_arn = os.getenv("SNS_TOPIC_ARN", "").strip()

    subject = f"[GATE PASS ALERT] New Request #{pass_id} from {name}"
    message = (
        f"NEW GATE PASS REQUEST SUBMITTED\n"
        f"--------------------------------\n"
        f"Pass ID             : #{pass_id}\n"
        f"Student Name        : {name}\n"
        f"Email               : {email}\n"
        f"Reason              : {reason}\n"
        f"Departure (Out)     : {out_time}\n"
        f"Expected Return     : {return_time}\n\n"
        f"Action Required: Please visit the Admin Dashboard to review and approve/reject this pass."
    )

    if not topic_arn:
        logger.warning("SNS_TOPIC_ARN not set. Simulating SNS alert to admin.")
        return {
            "success": True,
            "simulated": True,
            "message": f"(Simulated SNS) Admin alerted for new request #{pass_id} from {name}",
        }

    try:
        client = get_sns_client()
        response = client.publish(
            TopicArn=topic_arn,
            Subject=subject[:100],  # SNS subjects capped at 100 chars
            Message=message,
        )
        message_id = response.get("MessageId", "unknown")
        logger.info(f"SNS admin alert sent successfully. Message ID: {message_id}")
        return {
            "success": True,
            "simulated": False,
            "message_id": message_id,
            "message": f"Admin notified via SNS (Message ID: {message_id})",
        }
    except (BotoCoreError, ClientError) as e:
        error_msg = f"Failed to send SNS alert to admin: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "simulated": False,
            "error": error_msg,
            "message": "Notice: SNS notification could not be delivered to admin.",
        }
