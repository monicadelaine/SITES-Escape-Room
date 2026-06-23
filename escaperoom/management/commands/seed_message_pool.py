"""
python manage.py seed_message_pool

Seeds the MessagePool table with a default set of cipher messages and LLM secrets.
Safe to run multiple times — skips values that already exist.
"""
from django.core.management.base import BaseCommand

DEFAULT_CIPHER_MESSAGES = [
    "THE SECRET IS HIDDEN INSIDE THE RED BINDER ON THE SHELF",
    "LOOK UNDERNEATH THE KEYBOARD FOR YOUR NEXT CLUE",
    "THE ANSWER YOU NEED IS THE YEAR THE INTERNET WAS INVENTED",
    "CONGRATULATIONS YOU HAVE BROKEN THE CODE NOW FIND THE USB DRIVE",
    "THE PASSWORD IS THE NUMBER OF PLANETS IN OUR SOLAR SYSTEM",
    "CHECK THE WHITEBOARD IN THE CORNER FOR THE FINAL CLUE",
    "YOUR NEXT CHALLENGE IS WAITING ON THE BLUE TABLE BY THE WINDOW",
    "THE COMBINATION IS ONE NINE EIGHT FOUR",
    "WELL DONE TEAM THE NEXT CLUE IS UNDER THE LAPTOP",
    "THE KEY TO THE FINAL DOOR IS HIDDEN IN PLAIN SIGHT",
]

DEFAULT_LLM_SECRETS = [
    "2719", "8043", "5160", "3392", "7481", "6204",
    "9137", "4856", "1023", "7765", "3318", "9902",
    "4471", "6680", "2255",
]


class Command(BaseCommand):
    help = "Seed the MessagePool with default cipher messages and LLM secrets."

    def handle(self, *args, **options):
        from escaperoom.models import MessagePool

        added = 0
        for msg in DEFAULT_CIPHER_MESSAGES:
            _, created = MessagePool.objects.get_or_create(
                pool_type="cipher_message",
                value=msg,
            )
            if created:
                added += 1

        for secret in DEFAULT_LLM_SECRETS:
            _, created = MessagePool.objects.get_or_create(
                pool_type="llm_secret",
                value=secret,
            )
            if created:
                added += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {added} new entries into MessagePool "
            f"({len(DEFAULT_CIPHER_MESSAGES)} cipher messages, {len(DEFAULT_LLM_SECRETS)} LLM secrets)."
        ))
