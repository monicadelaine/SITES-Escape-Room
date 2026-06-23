from django.conf import settings
from django.db import models


class Session(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Team(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=80)
    password_hash = models.CharField(max_length=200)
    roster_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("session", "name")

    def __str__(self):
        return f"{self.name} ({self.session.slug})"


class TeamMember(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    name = models.CharField(max_length=80)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} — {self.team.name}"


class Activity(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="activities")
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    input_type = models.CharField(max_length=30)
    grader_type = models.CharField(max_length=30)
    config = models.JSONField()

    class Meta:
        ordering = ["order"]
        unique_together = ("session", "order")

    def __str__(self):
        return f"{self.session.slug} — {self.order}. {self.title}"


class TeamActivityProgress(models.Model):
    STATUS = [
        ("locked", "Locked"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="progress")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="progress")
    status = models.CharField(max_length=12, choices=STATUS, default="locked")
    attempts = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    config_override = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("team", "activity")

    def __str__(self):
        return f"{self.team.name} / {self.activity.title}: {self.status}"


class AttemptLog(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="attempts")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="attempts")
    submitted_at = models.DateTimeField(auto_now_add=True)
    payload = models.TextField()
    passed = models.BooleanField(null=True)
    detail = models.TextField(blank=True)
    error_trace = models.TextField(blank=True)
    manual_override = models.BooleanField(default=False)
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="overrides",
    )

    class Meta:
        ordering = ["submitted_at"]

    def __str__(self):
        status = "pass" if self.passed else ("pending" if self.passed is None else "fail")
        return f"{self.team.name}/{self.activity.title} @ {self.submitted_at:%H:%M:%S} [{status}]"


class LLMMessage(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="llm_messages")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="llm_messages")
    role = models.CharField(max_length=10)  # "user" / "model"
    content = models.TextField()
    blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        tag = " [BLOCKED]" if self.blocked else ""
        return f"{self.team.name}/{self.role}{tag}: {self.content[:60]}"


class MessagePool(models.Model):
    POOL_TYPES = [
        ("cipher_message", "Cipher Message"),
        ("llm_secret", "LLM Secret"),
    ]
    pool_type = models.CharField(max_length=20, choices=POOL_TYPES)
    value = models.CharField(max_length=500)
    last_used_at = models.DateTimeField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["last_used_at", "id"]

    def __str__(self):
        return f"[{self.pool_type}] {self.value[:60]}"


class SessionAuditLog(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="audit_log")
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=40)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.session.slug} / {self.action} @ {self.created_at:%H:%M:%S}"
