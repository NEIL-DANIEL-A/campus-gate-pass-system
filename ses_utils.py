"""
SES Utility Module for Campus Gate Pass System.
Handles sending transactional status notification emails to students using Amazon SES.
"""

import os
import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL", "security-office@campus.edu")


def get_ses_client():
    """Initializes and returns a boto3 SES client."""
    kwargs = {"region_name": AWS_REGION}
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if aws_access_key and aws_secret_key:
        kwargs["aws_access_key_id"] = aws_access_key
        kwargs["aws_secret_access_key"] = aws_secret_key
    return boto3.client("ses", **kwargs)


def send_pass_email(
    to_email: str,
    status: str,
    reason: str = None,
    out_time: str = None,
    return_time: str = None,
    name: str = "Student",
) -> dict:
    """
    Builds and sends an appropriately worded email to the student depending on approved/rejected status.

    Parameters:
      to_email: Recipient student's email address
      status: "approved" or "rejected"
      reason: Rejection reason if rejected
      out_time: Approved departure time
      return_time: Approved expected return time
      name: Student name
    """
    sender = os.getenv("SES_SENDER_EMAIL", "").strip() or "security-office@campus.edu"

    if status.lower() == "approved":
        subject = "Campus Gate Pass APPROVED - Official Digital Pass"
        body_text = (
            f"Dear {name},\n\n"
            f"Great news! Your campus gate pass request has been APPROVED by the campus administration.\n\n"
            f"Approved Departure Time : {out_time}\n"
            f"Expected Return Time    : {return_time}\n\n"
            f"Instructions:\n"
            f"1. Please display your digital pass status on your phone or provide your student ID to gate security.\n"
            f"2. Return to campus on or before {return_time}.\n\n"
            f"Safe travels,\n"
            f"Campus Security & Administration"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #2d3748; }}
    .container {{ max-width: 580px; margin: 20px auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
    .header {{ background-color: #047857; color: #ffffff; padding: 20px; text-align: center; }}
    .badge {{ display: inline-block; background-color: #10b981; color: white; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 14px; }}
    .content {{ padding: 24px; background: #ffffff; }}
    .details {{ background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 14px 18px; margin: 18px 0; border-radius: 4px; }}
    .footer {{ font-size: 12px; color: #718096; text-align: center; padding: 16px; background-color: #f7fafc; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h2 style="margin: 0;">Campus Gate Pass System</h2>
    </div>
    <div class="content">
      <p>Dear <strong>{name}</strong>,</p>
      <p>Your campus gate pass request has been <span class="badge">APPROVED</span>.</p>
      <div class="details">
        <p style="margin: 6px 0;"><strong>Departure Time:</strong> {out_time}</p>
        <p style="margin: 6px 0;"><strong>Expected Return:</strong> {return_time}</p>
      </div>
      <p>Please present your student ID or your pass status screen to the security officer at the main gate.</p>
      <p>Make sure to report back to campus prior to <strong>{return_time}</strong>.</p>
    </div>
    <div class="footer">
      Automated email powered by Amazon SES &bull; Campus Security Administration
    </div>
  </div>
</body>
</html>"""
    else:
        subject = "Campus Gate Pass Update: Request Rejected"
        reason_display = reason if reason else "No specific reason provided."
        body_text = (
            f"Dear {name},\n\n"
            f"We regret to inform you that your campus gate pass request has been REJECTED.\n\n"
            f"Reason for rejection:\n{reason_display}\n\n"
            f"If you believe this was an error or have urgent circumstances, please visit the administration desk.\n\n"
            f"Regards,\n"
            f"Campus Administration"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #2d3748; }}
    .container {{ max-width: 580px; margin: 20px auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
    .header {{ background-color: #b91c1c; color: #ffffff; padding: 20px; text-align: center; }}
    .badge {{ display: inline-block; background-color: #ef4444; color: white; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 14px; }}
    .content {{ padding: 24px; background: #ffffff; }}
    .details {{ background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 14px 18px; margin: 18px 0; border-radius: 4px; }}
    .footer {{ font-size: 12px; color: #718096; text-align: center; padding: 16px; background-color: #f7fafc; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h2 style="margin: 0;">Campus Gate Pass System</h2>
    </div>
    <div class="content">
      <p>Dear <strong>{name}</strong>,</p>
      <p>Your campus gate pass request was <span class="badge">REJECTED</span>.</p>
      <div class="details">
        <p style="margin: 6px 0;"><strong>Reason:</strong></p>
        <p style="margin: 6px 0; color: #991b1b;">{reason_display}</p>
      </div>
      <p>If you have questions or believe this is an error, please visit the security administration desk in person.</p>
    </div>
    <div class="footer">
      Automated email powered by Amazon SES &bull; Campus Security Administration
    </div>
  </div>
</body>
</html>"""

    # If sender email isn't configured or matches placeholder, simulate sending
    if not sender or sender == "security-office@campus.edu":
        logger.warning("SES_SENDER_EMAIL is not a real verified address. Simulating SES send.")
        return {
            "success": True,
            "simulated": True,
            "message": f"(Simulated SES email) Sent '{subject}' to {to_email}",
        }

    try:
        client = get_ses_client()
        response = client.send_email(
            Source=sender,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body_text, "Charset": "UTF-8"},
                    "Html": {"Data": body_html, "Charset": "UTF-8"},
                },
            },
        )
        message_id = response.get("MessageId", "unknown")
        logger.info(f"SES email sent to {to_email}. Message ID: {message_id}")
        return {
            "success": True,
            "simulated": False,
            "message_id": message_id,
            "message": f"Confirmation email sent to {to_email} via SES (ID: {message_id}).",
        }
    except (BotoCoreError, ClientError) as e:
        error_msg = f"Failed to send SES email to {to_email}: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "simulated": False,
            "error": error_msg,
            "message": f"Notice: Email to {to_email} could not be delivered via AWS SES.",
        }
