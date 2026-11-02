"""Terminal simulator:  python manage.py chat   (leads are saved to the DB, visible in /admin)."""

import re

from django.core.management.base import BaseCommand

from bot import services


class Command(BaseCommand):
    help = "Chat with the Autoveer bot in the terminal (no WhatsApp needed)."

    def add_arguments(self, parser):
        parser.add_argument("--phone", help="pretend to be this WhatsApp number (skips the phone question)")
        parser.add_argument("--name", help="pretend WhatsApp profile name")

    def handle(self, *args, **opts):
        user = f"cli:{opts['phone'] or 'local'}"
        services.reset_session(user)
        self.stdout.write(self.style.HTTP_INFO('Autoveer bot simulator. Type "hi" to begin, Ctrl+C to quit.\n'))
        while True:
            try:
                text = input("\033[32myou ›\033[0m ")
            except (EOFError, KeyboardInterrupt):
                self.stdout.write("\nbye!")
                return
            result = services.process_message(user, text, channel="cli", phone=opts["phone"], push_name=opts["name"])
            for r in result.replies:
                body = re.sub(r"\*([^*\n]+)\*", "\033[1m\\1\033[22m", r["text"])
                body = re.sub(r"_([^_\n]+)_", "\033[2m\\1\033[22m", body)
                self.stdout.write("\n\033[36mbot ›\033[0m " + body.replace("\n", "\n      "))
            if result.staff_message:
                self.stdout.write(self.style.WARNING("\n[staff notification]\n") + result.staff_message)
            self.stdout.write("")
