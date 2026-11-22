"""Runs on every deploy: makes the settings row and, the first time, the office login from ADMIN_USERNAME / ADMIN_PASSWORD."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from web.models import SiteSettings


class Command(BaseCommand):
    help = "Create the website settings row and the first office login."

    def handle(self, *args, **opts):
        SiteSettings.get()
        name, pw = os.environ.get("ADMIN_USERNAME"), os.environ.get("ADMIN_PASSWORD")
        User = get_user_model()
        if name and pw and not User.objects.filter(username=name).exists():
            User.objects.create_superuser(name, os.environ.get("OFFICE_EMAIL", ""), pw)
            self.stdout.write(f"Office login '{name}' created.")
        self.stdout.write("Website setup done.")
