import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

DEFAULT_EMAIL = "amitt@demil.in"
DEFAULT_FIRST = "Amitt"
DEFAULT_LAST = "Gupta"


class Command(BaseCommand):
    help = (
        "Seed the Super Admin account (idempotent). Credentials come from SUPERADMIN_EMAIL, "
        "SUPERADMIN_PASSWORD, SUPERADMIN_FIRST_NAME and SUPERADMIN_LAST_NAME; without "
        "SUPERADMIN_PASSWORD a new account gets a random password that is printed once."
    )

    def handle(self, *args, **options):
        email = os.environ.get("SUPERADMIN_EMAIL") or DEFAULT_EMAIL
        password = os.environ.get("SUPERADMIN_PASSWORD", "")
        first_name = os.environ.get("SUPERADMIN_FIRST_NAME") or DEFAULT_FIRST
        last_name = os.environ.get("SUPERADMIN_LAST_NAME") or DEFAULT_LAST

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "role": User.Role.SUPERADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        user.first_name = first_name
        user.last_name = last_name
        user.role = User.Role.SUPERADMIN
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True

        generated = ""
        if password:
            user.set_password(password)
        elif created:
            generated = secrets.token_urlsafe(12)
            user.set_password(generated)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} Super Admin: {email}"))
        if generated:
            message = f"Generated password (shown once, change it after login): {generated}"
            self.stdout.write(self.style.WARNING(message))
