import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


class EmailSender:
    """
    Production-grade branded email sender.
    """

    def __init__(self):
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    # -------------------------------------------------
    def _build_html(self, candidate_name, decision):
        if decision == "confirm":
            badge_color = "#16a34a"
            title = "You're Shortlisted!"
            message = (
                "Congratulations! Your profile stood out strongly "
                "against our requirements. Our hiring team will "
                "contact you with next steps shortly."
            )
        else:
            badge_color = "#dc2626"
            title = "Application Update"
            message = (
                "Thank you for taking the time to apply. "
                "After careful evaluation, we will not be "
                "moving forward at this time."
            )

        html = f"""
        <div style="font-family:Inter,Segoe UI,Arial;background:#f4f6f8;padding:40px">
          <div style="max-width:620px;margin:auto;background:#ffffff;
                      border-radius:14px;padding:32px;
                      box-shadow:0 10px 30px rgba(0,0,0,0.08)">

            <h2 style="margin:0;color:#111827;">Jatin Rajani Hiring</h2>

            <div style="margin:22px 0;">
              <span style="
                background:{badge_color};
                color:white;
                padding:6px 14px;
                border-radius:999px;
                font-size:13px;
                font-weight:600;">
                {title}
              </span>
            </div>

            <p style="color:#374151;font-size:15px;">
              Hi <strong>{candidate_name}</strong>,
            </p>

            <p style="color:#4b5563;font-size:15px;line-height:1.6;">
              {message}
            </p>

            <div style="margin-top:28px;padding-top:18px;
                        border-top:1px solid #e5e7eb;
                        color:#6b7280;font-size:13px;">
              This is an automated message from the
              <strong>AI Resume Screening System</strong>.
            </div>

          </div>
        </div>
        """
        return html

    # -------------------------------------------------
    def send_email(self, to_email, candidate_name, decision):
        """
        Returns (success: bool, message: str)
        """
        try:
            if not self.sender_email or not self.sender_password:
                return False, "Email credentials missing in .env"

            msg = MIMEMultipart("alternative")
            msg["From"] = self.sender_email
            msg["To"] = to_email
            msg["Subject"] = (
                "Application Update — Shortlisted 🎉"
                if decision == "confirm"
                else "Regarding Your Application"
            )

            html_body = self._build_html(candidate_name, decision)
            msg.attach(MIMEText(html_body, "html"))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()

            return True, "Email sent successfully"

        except smtplib.SMTPAuthenticationError:
            return False, "SMTP authentication failed (check App Password)"

        except Exception as e:
            return False, f"Email error: {str(e)}"
