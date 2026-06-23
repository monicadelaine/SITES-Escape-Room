"""
Input type registry.  Each input type knows how to:
  - build the template context for the student-facing form
  - parse the raw answer out of a POST request
"""
import json
import random

INPUT_REGISTRY = {}


def register_input(key):
    def wrap(cls):
        INPUT_REGISTRY[key] = cls
        return cls
    return wrap


class BaseInput:
    def get_form_context(self, activity, team, progress):
        """Return extra context dict for the activity template."""
        return {}

    def parse_submission(self, request):
        """Return the raw answer value from POST data."""
        raise NotImplementedError

    @property
    def template_name(self):
        raise NotImplementedError


@register_input("blank_fill")
class BlankFillInput(BaseInput):
    template_name = "escaperoom/activity_blank_fill.html"

    def get_form_context(self, activity, team, progress):
        from .graders import resolve_config
        cfg = resolve_config(activity, team)
        template_code = cfg.get("template", "")
        # Split on the blank marker so the template can render before/after
        parts = template_code.split("___BLANK___", 1)
        code_before = parts[0] if parts else ""
        code_after = parts[1] if len(parts) > 1 else ""
        return {
            "code_template": template_code,
            "code_before": code_before,
            "code_after": code_after,
        }

    def parse_submission(self, request):
        return request.POST.get("blank_answer", "").strip()


@register_input("code_editor")
class CodeEditorInput(BaseInput):
    template_name = "escaperoom/activity_code_editor.html"

    def get_form_context(self, activity, team, progress):
        from .graders import resolve_config
        cfg = resolve_config(activity, team)
        return {"starter_code": cfg.get("starter_code", "")}

    def parse_submission(self, request):
        return request.POST.get("code", "").strip()


@register_input("integer")
class IntegerInput(BaseInput):
    template_name = "escaperoom/activity_integer.html"

    def get_form_context(self, activity, team, progress):
        from .graders import resolve_config
        cfg = resolve_config(activity, team)
        # derive ciphertext at render time
        plaintext = cfg.get("plaintext", "")
        shift = cfg.get("shift", 0)
        from .graders import caesar_encode
        ciphertext = caesar_encode(plaintext, shift)
        first_word = plaintext.split()[0] if cfg.get("first_word_hint") and plaintext else None
        return {
            "ciphertext": ciphertext,
            "first_word_hint": first_word,
        }

    def parse_submission(self, request):
        val = request.POST.get("shift_guess", "0").strip()
        try:
            return str(int(val))
        except ValueError:
            return "0"


@register_input("text")
class TextInput(BaseInput):
    template_name = "escaperoom/activity_text.html"

    def get_form_context(self, activity, team, progress):
        from .graders import resolve_config
        cfg = resolve_config(activity, team)
        return {"prompt": cfg.get("prompt", "")}

    def parse_submission(self, request):
        return request.POST.get("text_answer", "").strip()


@register_input("chat_plus_secret")
class ChatPlusSecretInput(BaseInput):
    template_name = "escaperoom/activity_chat_plus_secret.html"

    def get_form_context(self, activity, team, progress):
        from .models import LLMMessage
        from .graders import resolve_config
        cfg = resolve_config(activity, team)
        messages = LLMMessage.objects.filter(
            team=team, activity=activity, blocked=False
        ).order_by("created_at")
        msg_count = messages.filter(role="user").count()
        hint_after = cfg.get("hint_after_messages", None)
        hint_text = cfg.get("hint", "")
        show_hint = bool(hint_text and hint_after is not None and msg_count >= hint_after)
        return {
            "chat_messages": messages,
            "msg_count": msg_count,
            "hint": hint_text if show_hint else "",
            "hint_text": hint_text,
            "hint_after": hint_after,
        }

    def parse_submission(self, request):
        # This input type handles two separate POST actions:
        # "chat" (send a message) and "secret" (submit the guessed secret).
        # The view dispatcher checks POST["action"] and calls the correct path.
        return request.POST.get("secret_guess", "").strip()


@register_input("staff_only")
class StaffOnlyInput(BaseInput):
    template_name = "escaperoom/activity_staff_only.html"

    def get_form_context(self, activity, team, progress):
        from .graders import resolve_config
        cfg = resolve_config(activity, team)
        return {"instructions": cfg.get("instructions", "")}

    def parse_submission(self, request):
        return ""


@register_input("match_pairs")
class MatchPairsInput(BaseInput):
    template_name = "escaperoom/activity_match_pairs.html"

    def get_form_context(self, activity, team, progress):
        from .graders import resolve_config, _get_team_pairs
        cfg = resolve_config(activity, team)
        selected = _get_team_pairs(cfg, team, activity)

        # Scenarios in the team's deterministic order; idx is the original pair index
        scenario_items = [{"idx": idx, "scenario": pair["scenario"]} for idx, pair in selected]

        # Technique bank: techniques from selected pairs, shuffled independently
        techniques = [pair["technique"] for _, pair in selected]
        rng = random.Random(team.pk * 9973 + activity.pk)
        rng.shuffle(techniques)

        return {
            "scenario_items": scenario_items,
            "techniques": techniques,
            "description": cfg.get("description", ""),
        }

    def parse_submission(self, request):
        raw = request.POST.get("match_answer", "{}")
        try:
            data = json.loads(raw)
            return json.dumps({str(k): str(v) for k, v in data.items()})
        except (ValueError, TypeError):
            return "{}"


@register_input("pseudocode_order")
class PseudocodeOrderInput(BaseInput):
    template_name = "escaperoom/activity_pseudocode_order.html"

    def get_form_context(self, activity, team, progress):
        from .graders import resolve_config
        cfg = resolve_config(activity, team)
        lines = cfg.get("lines", [])

        # Deterministic shuffle per team+activity so a page refresh shows the same order
        rng = random.Random(team.pk * 7919 + activity.pk)
        shuffled_indices = list(range(len(lines)))
        rng.shuffle(shuffled_indices)

        line_items = [
            {"text": lines[i], "orig_idx": i}
            for i in shuffled_indices
        ]

        return {
            "line_items": line_items,
            "description": cfg.get("description", ""),
            "image_file": cfg.get("image_file", ""),
        }

    def parse_submission(self, request):
        order = request.POST.getlist("order")
        try:
            return json.dumps([int(x) for x in order])
        except (ValueError, TypeError):
            return "[]"
