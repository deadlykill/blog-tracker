import html
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_notification(updates: dict[str, list[dict]]) -> bool:
    """Send an email listing all new posts grouped by site.

    `updates` maps site_name -> list of {title, url, date?} dicts.
    Returns True if sent successfully, False otherwise.
    """
    email_addr = os.environ.get("EMAIL_ADDRESS", "")
    email_pass = os.environ.get("EMAIL_PASSWORD", "")
    notify_to = os.environ.get("NOTIFY_EMAIL", email_addr)

    if not email_addr or not email_pass:
        logger.warning(
            "Email credentials not configured. "
            "Set EMAIL_ADDRESS and EMAIL_PASSWORD environment variables."
        )
        _print_updates(updates)
        return False

    total = sum(len(posts) for posts in updates.values())
    subject = f"[Blog Tracker] {total} new post{'s' if total != 1 else ''} found"

    body_plain = _format_plain(updates)
    body_html = _format_html(updates)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_addr
    msg["To"] = notify_to
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(email_addr, email_pass)
            server.sendmail(email_addr, [notify_to], msg.as_string())
        logger.info("Notification email sent to %s", notify_to)
        return True
    except Exception as exc:
        logger.error("Failed to send email: %s", exc)
        _print_updates(updates)
        return False


def _format_plain(updates: dict[str, list[dict]]) -> str:
    lines = ["New blog posts detected:\n"]
    for site_name, posts in updates.items():
        lines.append(f"== {site_name} ==")
        for post in posts:
            date_part = f" ({post['date']})" if post.get("date") else ""
            lines.append(f'  - "{post["title"]}"{date_part}')
            lines.append(f"    {post['url']}")
        lines.append("")
    return "\n".join(lines)


def _format_html(updates: dict[str, list[dict]]) -> str:
    parts = [
        "<html><body>",
        "<h2>New blog posts detected</h2>",
    ]
    for site_name, posts in updates.items():
        parts.append(f"<h3>{html.escape(site_name)}</h3><ul>")
        for post in posts:
            safe_title = html.escape(post["title"])
            safe_url = html.escape(post["url"], quote=True)
            date_part = f" <em>({html.escape(post['date'])})</em>" if post.get("date") else ""
            parts.append(
                f'<li><a href="{safe_url}">{safe_title}</a>{date_part}</li>'
            )
        parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _print_updates(updates: dict[str, list[dict]]) -> None:
    """Fallback: print updates to stdout when email is not configured."""
    print("\n" + "=" * 60)
    print("NEW POSTS DETECTED (email not configured, printing to console)")
    print("=" * 60)
    print(_format_plain(updates))
