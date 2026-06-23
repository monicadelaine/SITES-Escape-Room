"""
python manage.py load_session path/to/session.json

Creates Session, Team, Activity, and TeamActivityProgress rows.
Handles team_overrides, shift_pool/secret_pool, and auto-fill from MessagePool.
"""
import json
import random
from datetime import datetime
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class Command(BaseCommand):
    help = "Load a session from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("json_file", type=str)
        parser.add_argument(
            "--force",
            action="store_true",
            help="If a session with this slug already exists, update it.",
        )

    def handle(self, *args, **options):
        from escaperoom.models import (
            Activity,
            MessagePool,
            Session,
            Team,
            TeamActivityProgress,
        )

        path = Path(options["json_file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        with open(path) as f:
            data = json.load(f)

        slug = data["slug"]
        name = data["session_name"]

        start_time = None
        if "start_time" in data:
            start_time = parse_datetime(data["start_time"])

        end_time = None
        if "end_time" in data:
            end_time = parse_datetime(data["end_time"])

        # Create or update session
        session, created = Session.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "start_time": start_time,
                "end_time": end_time,
            },
        )
        if not created:
            if not options["force"]:
                raise CommandError(
                    f"Session '{slug}' already exists. Use --force to update."
                )
            session.name = name
            session.start_time = start_time
            session.end_time = end_time
            session.save()
            self.stdout.write(f"Updated existing session: {slug}")
        else:
            self.stdout.write(f"Created session: {slug}")

        # Create teams
        teams = {}
        for t in data.get("teams", []):
            team, _ = Team.objects.get_or_create(
                session=session,
                name=t["name"],
                defaults={"password_hash": make_password(t["password"])},
            )
            if not _:
                team.password_hash = make_password(t["password"])
                team.save()
            teams[t["name"]] = team
            self.stdout.write(f"  Team: {t['name']}")

        team_list = list(teams.values())

        # Create activities and progress rows
        for act_data in data.get("activities", []):
            activity, _ = Activity.objects.update_or_create(
                session=session,
                order=act_data["order"],
                defaults={
                    "title": act_data["title"],
                    "input_type": act_data["input_type"],
                    "grader_type": act_data["grader_type"],
                    "config": act_data["config"],
                },
            )
            self.stdout.write(f"  Activity {act_data['order']}: {act_data['title']}")

            explicit_overrides = act_data.get("team_overrides", {})
            shift_pool = act_data.get("shift_pool", [])
            secret_pool = act_data.get("secret_pool", [])

            # Pre-generate per-team values if pools/auto-fill needed
            auto_shifts = _auto_shifts(len(team_list)) if activity.grader_type == "decode_compare" else []
            auto_secrets = _auto_secrets_from_pool(len(team_list)) if activity.grader_type == "secret_match" else []

            for i, team in enumerate(team_list):
                override = dict(explicit_overrides.get(team.name, {}))

                if activity.grader_type == "decode_compare":
                    # Shift pool takes precedence over auto
                    if "shift" not in override:
                        if shift_pool:
                            override["shift"] = shift_pool[i % len(shift_pool)]
                        elif not activity.config.get("shift"):
                            override["shift"] = auto_shifts[i]
                    # Auto-fill plaintext from cipher_message pool if missing
                    if "plaintext" not in override and not activity.config.get("plaintext"):
                        msg = _pull_from_pool("cipher_message")
                        if msg:
                            override["plaintext"] = msg

                elif activity.grader_type == "secret_match":
                    if "secret" not in override:
                        if secret_pool:
                            override["secret"] = secret_pool[i % len(secret_pool)]
                        elif not activity.config.get("secret"):
                            if i < len(auto_secrets):
                                override["secret"] = auto_secrets[i]

                TeamActivityProgress.objects.update_or_create(
                    team=team,
                    activity=activity,
                    defaults={
                        "status": "locked",
                        "attempts": 0,
                        "started_at": None,
                        "completed_at": None,
                        "config_override": override,
                    },
                )

        self.stdout.write(self.style.SUCCESS(f"Session '{slug}' loaded successfully."))


def _auto_shifts(n):
    """Generate n distinct random shifts (1–25)."""
    pool = list(range(1, 26))
    random.shuffle(pool)
    return (pool * (n // 25 + 1))[:n]


def _auto_secrets_from_pool(n):
    """Pull n secrets from the llm_secret MessagePool."""
    from escaperoom.models import MessagePool
    from django.utils import timezone
    entries = list(
        MessagePool.objects.filter(pool_type="llm_secret").order_by("last_used_at", "id")[:n]
    )
    secrets = []
    now = timezone.now()
    for e in entries:
        secrets.append(e.value)
        e.last_used_at = now
        e.times_used += 1
        e.save()
    return secrets


def _pull_from_pool(pool_type):
    from escaperoom.models import MessagePool
    from django.utils import timezone
    entry = MessagePool.objects.filter(pool_type=pool_type).order_by("last_used_at", "id").first()
    if entry:
        entry.last_used_at = timezone.now()
        entry.times_used += 1
        entry.save()
        return entry.value
    return None
