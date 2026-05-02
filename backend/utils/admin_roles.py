import os


def get_superadmin_emails():
    configured = (os.environ.get("SUPERADMIN_EMAILS") or "").strip()
    if configured:
        return {
            email.strip().lower()
            for email in configured.split(",")
            if email and email.strip()
        }

    default_admin_email = (os.environ.get("ADMIN_EMAIL") or "admin@grace-wise.com").strip().lower()
    return {default_admin_email} if default_admin_email else set()


def is_superadmin(user):
    if not user or not bool(getattr(user, "is_admin", False)):
        return False

    user_email = (getattr(user, "email", "") or "").strip().lower()
    if not user_email:
        return False

    return user_email in get_superadmin_emails()
