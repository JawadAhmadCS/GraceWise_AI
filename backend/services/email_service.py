import os
import smtplib
from email.message import EmailMessage


def _smtp_enabled():
    return bool(os.environ.get("SMTP_HOST")) and bool(os.environ.get("EMAIL_FROM"))


def _frontend_base_url():
    return (os.environ.get("FRONTEND_BASE_URL") or "http://localhost:5500").rstrip("/")


def send_email(to_email, subject, text_body):
    """
    Best-effort transactional email sender.
    If SMTP is not configured, the function logs and returns False.
    """
    if not _smtp_enabled():
        print(f"[Email disabled] To={to_email} Subject={subject}")
        return False

    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    from_email = os.environ.get("EMAIL_FROM")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(text_body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password or "")
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print(f"[Email send error] {exc}")
        return False


def send_welcome_email(user):
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip() or "there"
    body = (
        f"Hi {full_name},\n\n"
        "Welcome to GraceWise.\n\n"
        "You are all set to start building a calmer, more intentional homeschool week.\n"
        "When you are ready, choose your plan and we will personalize everything for your family.\n\n"
        f"Start here: {_frontend_base_url()}/premium-plan.html\n\n"
        "GraceWise Team"
    )
    return send_email(user.email, "Welcome to GraceWise", body)


def send_password_reset_email(user, token):
    reset_link = f"{_frontend_base_url()}/reset-password.html?token={token}"
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip() or "there"
    body = (
        f"Hi {full_name},\n\n"
        "We received a request to reset your GraceWise password.\n\n"
        f"Reset your password here: {reset_link}\n\n"
        "This link expires in 60 minutes. If you did not request this reset, you can ignore this email.\n\n"
        "GraceWise Team"
    )
    return send_email(user.email, "Reset your GraceWise password", body)


def send_payment_confirmation_email(user, plan_name, amount_text):
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip() or "there"
    body = (
        f"Hi {full_name},\n\n"
        "Your GraceWise subscription payment was successful.\n\n"
        f"Plan: {plan_name}\n"
        f"Amount: {amount_text}\n\n"
        "Thanks for trusting GraceWise to support your homeschool journey.\n\n"
        "GraceWise Team"
    )
    return send_email(user.email, "GraceWise payment confirmed", body)


def send_failed_payment_email(user):
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip() or "there"
    manage_link = f"{_frontend_base_url()}/settings.html"
    body = (
        f"Hi {full_name},\n\n"
        "We could not process your latest GraceWise subscription payment.\n\n"
        "Please update your payment method and retry the payment from your billing settings.\n"
        f"Manage billing: {manage_link}\n\n"
        "GraceWise Team"
    )
    return send_email(user.email, "GraceWise payment failed", body)


def send_invoice_receipt_email(user, invoice_url):
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip() or "there"
    body = (
        f"Hi {full_name},\n\n"
        "Your GraceWise invoice/receipt is ready.\n\n"
        f"View invoice: {invoice_url}\n\n"
        "GraceWise Team"
    )
    return send_email(user.email, "GraceWise invoice receipt", body)


def send_homeschool_style_result_email(email, result_payload):
    result_title = result_payload.get("result_title", "Your Homeschool Style")
    summary = result_payload.get("result_summary", "")
    strengths = result_payload.get("strengths", []) or []

    strengths_text = "\n".join(f"- {item}" for item in strengths) if strengths else "- Personalized recommendations are ready."

    body = (
        "Hi there,\n\n"
        "Your GraceWise homeschool style results are ready.\n\n"
        f"Result: {result_title}\n\n"
        f"{summary}\n\n"
        "Your strengths:\n"
        f"{strengths_text}\n\n"
        "We are cheering you on as you build a peaceful, purpose-filled homeschool.\n\n"
        "GraceWise Team"
    )
    return send_email(email, "Your GraceWise Homeschool Style Results", body)
