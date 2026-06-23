"""
Public status view — projector screen, no login required.
"""
import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Activity, Session, Team, TeamActivityProgress


def status_view(request, slug):
    session = get_object_or_404(Session, slug=slug)
    activities = list(Activity.objects.filter(session=session).order_by("order"))
    teams = list(Team.objects.filter(session=session).order_by("name"))

    rows = _build_grid(teams, activities)

    end_time_iso = session.end_time.isoformat() if session.end_time else None

    return render(request, "escaperoom/status.html", {
        "session": session,
        "activities": activities,
        "rows": rows,
        "end_time_iso": end_time_iso,
    })


def status_json(request, slug):
    session = get_object_or_404(Session, slug=slug)
    activities = list(Activity.objects.filter(session=session).order_by("order"))
    teams = list(Team.objects.filter(session=session).order_by("name"))

    rows = _build_grid(teams, activities)

    return JsonResponse({
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "is_active": session.is_active,
        "teams": rows,
    })


def _build_grid(teams, activities):
    rows = []
    for team in teams:
        progress_map = {
            p.activity_id: p
            for p in TeamActivityProgress.objects.filter(team=team)
        }
        cells = []
        for act in activities:
            p = progress_map.get(act.pk)
            cells.append({
                "activity_id": act.pk,
                "title": act.title,
                "status": p.status if p else "locked",
                "attempts": p.attempts if p else 0,
            })
        rows.append({
            "team_id": team.pk,
            "team_name": team.name,
            "cells": cells,
        })
    return rows
