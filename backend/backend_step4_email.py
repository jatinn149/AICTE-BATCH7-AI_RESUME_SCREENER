import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Tuple
from dotenv import load_dotenv

load_dotenv()


class EmailSender:
    """
    Production-grade branded email sender.
    """

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    VALID_DECISIONS = {"confirm", "reject"}
    SUBJECT_BY_DECISION = {
        "confirm": "Application Update — Shortlisted 🎉",
        "reject": "Regarding Your Application",
    }
    CONTENT_BY_DECISION = {
        "confirm": {
            "accent_color": "#166534",
            "soft_color": "#dcfce7",
            "title": "You're Shortlisted!",
            "message": (
                "Congratulations! Your profile stood out strongly "
                "against our requirements. Our hiring team will "
                "contact you with next steps shortly."
            ),
            "status_label": "Accepted",
        },
        "reject": {
            "accent_color": "#991b1b",
            "soft_color": "#fee2e2",
            "title": "Application Update",
            "message": (
                "Thank you for taking the time to apply. "
                "After careful evaluation, we will not be "
                "moving forward at this time."
            ),
            "status_label": "Not Selected",
        },
    }

    def __init__(self):
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
        self.smtp_server = self.SMTP_SERVER
        self.smtp_port = self.SMTP_PORT

    def _resolve_email_content(self, decision):
        return self.CONTENT_BY_DECISION.get(decision, self.CONTENT_BY_DECISION["reject"])

    def _resolve_subject(self, decision):
        return self.SUBJECT_BY_DECISION.get(decision, self.SUBJECT_BY_DECISION["reject"])

    # -------------------------------------------------
    def _build_html(self, candidate_name, decision):
        content = self._resolve_email_content(decision)

        html = f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f1f5f9;padding:24px 12px;font-family:Segoe UI,Arial,sans-serif;">
            <tr>
                <td align="center">
                    <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:640px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">
                        <tr>
                            <td style="padding:0;">
                                <div style="background:{content['accent_color']};padding:20px 28px;color:#ffffff;">
                                    <div style="font-size:20px;font-weight:700;letter-spacing:0.2px;">Jatin Rajani Hiring</div>
                                    <div style="font-size:13px;opacity:0.9;margin-top:4px;">AI Resume Screening System</div>
                                </div>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:28px 28px 8px 28px;">
                                <span style="display:inline-block;background:{content['soft_color']};color:{content['accent_color']};padding:7px 14px;border-radius:999px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.4px;">
                                    {content['status_label']}
                                </span>
                                <h2 style="margin:16px 0 0 0;color:#0f172a;font-size:26px;line-height:1.25;">{content['title']}</h2>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:16px 28px 8px 28px;">
                                <p style="margin:0;color:#1e293b;font-size:16px;line-height:1.6;">Hi <strong>{candidate_name}</strong>,</p>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:0 28px 20px 28px;">
                                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px 18px;color:#334155;font-size:15px;line-height:1.7;">
                                    {content['message']}
                                </div>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:4px 28px 26px 28px;">
                                <p style="margin:0;color:#64748b;font-size:13px;line-height:1.6;">
                                    If you have any questions, feel free to reply to this email.
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:16px 28px;border-top:1px solid #e2e8f0;background:#f8fafc;color:#64748b;font-size:12px;line-height:1.6;">
                                This is an automated message from the <strong>AI Resume Screening System</strong>.
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        """
        return html

    def _validate_send_input(self, to_email, candidate_name, decision) -> Tuple[bool, str, Optional[str]]:
        if not to_email or "@" not in to_email:
            return False, "Invalid email address", "invalid_email"

        normalized_name = (candidate_name or "").strip()
        if len(normalized_name) < 1:
            return False, "Invalid candidate name", "invalid_name"

        if decision not in self.VALID_DECISIONS:
            return False, "Invalid decision type", "invalid_decision"

        if not self.sender_email or not self.sender_password:
            return False, "Email credentials not configured", "no_credentials"

        return True, "ok", None

    def _build_email_message(self, to_email, candidate_name, decision):
        msg = MIMEMultipart("alternative")
        msg["From"] = self.sender_email
        msg["To"] = to_email
        msg["Subject"] = self._resolve_subject(decision)

        html_body = self._build_html(candidate_name, decision)
        msg.attach(MIMEText(html_body, "html"))
        return msg

    def _send_via_smtp(self, message):
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(message)

    # -------------------------------------------------
    def send_email(self, to_email, candidate_name, decision):
        """
        Returns (success: bool, message: str, error_code: str|None)
        """
        try:
            is_valid, validation_message, validation_code = self._validate_send_input(
                to_email,
                candidate_name,
                decision,
            )
            if not is_valid:
                return False, validation_message, validation_code

            message = self._build_email_message(to_email, candidate_name, decision)
            self._send_via_smtp(message)

            return True, "Email sent successfully", None

        except smtplib.SMTPAuthenticationError as e:
            error_msg = "SMTP authentication failed (check App Password)"
            print(f"[EMAIL AUTH ERROR] {error_msg}: {str(e)}")
            return False, error_msg, "auth_failed"

        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            print(f"[EMAIL SMTP ERROR] {error_msg}")
            return False, error_msg, "smtp_error"

        except ConnectionError as e:
            error_msg = "Failed to connect to email server (network issue)"
            print(f"[EMAIL CONNECTION ERROR] {error_msg}: {str(e)}")
            return False, error_msg, "connection_error"

        except Exception as e:
            error_msg = f"Unexpected email error: {str(e)}"
            print(f"[EMAIL ERROR] {error_msg}")
            return False, error_msg, "unknown_error"
