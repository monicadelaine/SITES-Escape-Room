"""
python manage.py export_session <slug> [--output path.json]

Writes the session's full resolved state back to JSON in the same shape
that load_session accepts.
"""
import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Export a session to JSON."

    def add_arguments(self, parser):
        parser.add_argument("slug", type=str)
        parser.add_argument("--output", type=str, default=None)

    def handle(self, *args, **options):
        from escaperoom.models import Activity, Session, Team, TeamActivityProgress

        slug = options["slug"]
        try:
            session = Session.objects.get(slug=slug)
        except Session.DoesNotExist:
            raise CommandError(f"Session '{slug}' not found.")

        teams = list(Team.objects.filter(session=session).order_by("name"))
        activities = list(Activity.objects.filter(session=session).order_by("order"))

        team_data = [{"name": t.name, "password": "[hashed — reset if re-loading]"} for t in teams]

        activity_data = []
        for act in activities:
            team_overrides = {}
            for team in teams:
                try:
                    p = TeamActivityProgress.objects.get(team=team, activity=act)
                    if p.config_override:
                        team_overrides[team.name] = p.config_override
                except TeamActivityProgress.DoesNotExist:
                    pass

            entry = {
                "order": act.order,
                "title": act.title,
                "input_type": act.input_type,
                "grader_type": act.grader_type,
                "config": act.config,
            }
            if team_overrides:
                entry["team_overrides"] = team_overrides
            activity_data.append(entry)

        output = {
            "session_name": session.name,
            "slug": session.slug,
            "teams": team_data,
            "activities": activity_data,
        }
        if session.start_time:
            output["start_time"] = session.start_time.isoformat()
        if session.end_time:
            output["end_time"] = session.end_time.isoformat()

        json_str = json.dumps(output, indent=2)

        out_path = options.get("output")
        if out_path:
            Path(out_path).write_text(json_str)
            self.stdout.write(self.style.SUCCESS(f"Exported to {out_path}"))
        else:
            self.stdout.write(json_str)
