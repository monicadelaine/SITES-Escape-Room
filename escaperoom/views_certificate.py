"""
Certificate generation — WeasyPrint HTML → PDF.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Activity, Session, Team, TeamActivityProgress


def certificate_view(request, slug):
    session = get_object_or_404(Session, slug=slug)
    team_id = request.session.get("team_id")
    if not team_id or request.session.get("session_id") != session.pk:
        return redirect("login", slug=slug)

    team = get_object_or_404(Team, pk=team_id, session=session)

    activities = list(Activity.objects.filter(session=session).order_by("order"))
    progress_map = {
        p.activity_id: p
        for p in TeamActivityProgress.objects.filter(team=team)
    }

    total = len(activities)
    completed_count = sum(
        1 for a in activities
        if progress_map.get(a.pk) and progress_map[a.pk].status == "completed"
    )
    all_completed = completed_count == total

    now = timezone.now()
    session_ended = (
        not session.is_active
        or (session.end_time and now >= session.end_time)
    )

    # Determine which certificate (if any) the team has earned
    if all_completed:
        kind = "completion"
    elif session_ended:
        kind = "participation"
    else:
        # No certificate yet — redirect back to play
        return redirect("play", slug=slug)

    members = list(team.members.order_by("order"))

    # Compute elapsed time
    if kind == "completion":
        last_completed = max(
            (progress_map[a.pk].completed_at for a in activities if progress_map.get(a.pk)),
            default=now,
        )
        elapsed = last_completed - (team.roster_completed_at or last_completed)
    else:
        end_ref = session.end_time if session.end_time else now
        elapsed = end_ref - (team.roster_completed_at or end_ref)

    elapsed_str = _fmt_duration(elapsed)

    # Build completed / not-completed lists for participation cert
    completed_activities = [
        a for a in activities
        if progress_map.get(a.pk) and progress_map[a.pk].status == "completed"
    ]
    incomplete_activities = [
        a for a in activities
        if not (progress_map.get(a.pk) and progress_map[a.pk].status == "completed")
    ]

    context = {
        "session": session,
        "team": team,
        "members": members,
        "kind": kind,
        "completed_count": completed_count,
        "total": total,
        "elapsed": elapsed_str,
        "completed_activities": completed_activities,
        "incomplete_activities": incomplete_activities,
        "completion_date": now.strftime("%B %d, %Y"),
    }

    template_name = (
        "escaperoom/certificates/completion.html"
        if kind == "completion"
        else "escaperoom/certificates/participation.html"
    )
    html_string = render_to_string(template_name, context, request=request)

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri("/")).write_pdf()
        suffix = "" if kind == "completion" else "-participation"
        filename = f"{team.name}-certificate{suffix}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except ImportError:
        # WeasyPrint not installed — serve the HTML preview instead
        return HttpResponse(html_string)


def _fmt_duration(td):
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {seconds}s"
