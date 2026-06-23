"""
Grader registry.  Each grader is a callable:
    grader(activity, team, payload) -> (passed, detail, extra_data)

  passed:     True/False/None (None = pending staff review)
  detail:     string shown to the team
  extra_data: dict of extra info (not directly shown, used by views)
"""
import logging
import random
import re
import subprocess
import sys
import traceback

logger = logging.getLogger("escaperoom.attempts")

GRADER_REGISTRY = {}


def register_grader(key):
    def wrap(fn):
        GRADER_REGISTRY[key] = fn
        return fn
    return wrap


def resolve_config(activity, team):
    """
    Merge team's config_override on top of the activity's base config.
    Call this in every grader and input renderer instead of reading
    activity.config directly.
    """
    from .models import TeamActivityProgress
    progress = TeamActivityProgress.objects.get(team=team, activity=activity)
    return {**activity.config, **progress.config_override}


# ---------------------------------------------------------------------------
# Caesar cipher helpers
# ---------------------------------------------------------------------------

def caesar_encode(text, shift):
    result = []
    for ch in text.upper():
        if ch.isalpha():
            result.append(chr((ord(ch) - ord("A") + shift) % 26 + ord("A")))
        else:
            result.append(ch)
    return "".join(result)


def caesar_decode(text, shift):
    return caesar_encode(text, -shift)


# ---------------------------------------------------------------------------
# Graders
# ---------------------------------------------------------------------------

# Banned tokens for the blank_fill sandbox check
_BANNED_TOKENS = re.compile(
    r"\b(import|exec|eval|open|input|__\w+__|subprocess)\b|os\.|sys\."
)


@register_grader("test_case_runner")
def grade_test_cases(activity, team, payload):
    """
    Validates one student-supplied line by splicing it into the fixed
    template and running against random test cases in a subprocess.
    """
    config = resolve_config(activity, team)
    template = config.get("template", "")
    blank_pattern = config.get("blank_pattern", "")
    num_cases = config.get("test_cases", 5)

    # Safety check — reject dangerous tokens before any execution
    if _BANNED_TOKENS.search(payload):
        return False, "Submission contains a disallowed keyword — check your answer.", {}

    # Splice the student line into the template
    filled = template.replace("___BLANK___", payload)

    passed_count = 0
    errors = []

    for _ in range(num_cases):
        numbers = [random.randint(1, 999) for _ in range(10)]
        expected = max(numbers)

        harness = f"def generate_numbers():\n    return {numbers}\n{filled}"

        try:
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-c", harness],
                capture_output=True,
                text=True,
                timeout=3,
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode != 0:
                msg = stderr.splitlines()[-1] if stderr else "Runtime error"
                if "IndentationError" in stderr or "SyntaxError" in stderr:
                    return False, "Check your indentation on the line you added.", {}
                errors.append(msg)
            elif stdout == str(expected):
                passed_count += 1
            else:
                errors.append(f"Got {stdout!r}, expected {expected}")
        except subprocess.TimeoutExpired:
            return False, "Code took too long to run (possible infinite loop).", {}
        except Exception as exc:
            return False, "Unexpected error running your code.", {"_exc": str(exc)}

    if passed_count == num_cases:
        return True, f"✓ {num_cases}/{num_cases} test cases passed.", {"passed_count": passed_count}

    detail = f"{passed_count}/{num_cases} test cases passed."
    if errors:
        detail += f" Last error: {errors[-1]}"
    return False, detail, {"passed_count": passed_count}


@register_grader("decode_compare")
def grade_cipher_shift(activity, team, payload):
    config = resolve_config(activity, team)
    try:
        shift = int(payload) % 26
    except (ValueError, TypeError):
        return False, "Please enter a number 0–25.", {}

    plaintext = config.get("plaintext", "")
    correct_shift = config.get("shift", 0)
    ciphertext = caesar_encode(plaintext, correct_shift)
    decoded = caesar_decode(ciphertext, shift)

    passed = decoded.strip().upper() == plaintext.strip().upper()
    return passed, decoded, {"decoded_text": decoded, "ciphertext": ciphertext}


@register_grader("secret_match")
def grade_secret(activity, team, payload):
    config = resolve_config(activity, team)
    secret = config.get("secret", "")
    passed = payload.strip().lower() == secret.strip().lower()
    return passed, "", {}


@register_grader("manual_staff")
def grade_manual(activity, team, payload):
    return None, "Awaiting staff confirmation.", {}


def _get_team_pairs(cfg, team, activity):
    """
    Return the deterministic subset and display order of pairs for this team+activity.
    If config["scenario_count"] < len(pairs), a random subset is selected.
    Returns a list of (original_index, pair_dict).
    """
    pairs = cfg.get("pairs", [])
    count = min(cfg.get("scenario_count", len(pairs)), len(pairs))
    rng = random.Random(team.pk * 6271 + activity.pk)
    indices = rng.sample(range(len(pairs)), count)
    return [(idx, pairs[idx]) for idx in indices]


@register_grader("match_grader")
def grade_match(activity, team, payload):
    """
    Match-pairs grader.  payload is a JSON string like {"0":"Urgency","1":"Authority",...}
    mapping original pair index (str) → submitted technique name.
    Uses the same deterministic subset as the input handler.
    """
    import json as _json
    config = resolve_config(activity, team)
    selected = _get_team_pairs(config, team, activity)

    try:
        submitted = _json.loads(payload) if isinstance(payload, str) else {}
    except (ValueError, TypeError):
        submitted = {}

    per_slot = {}
    correct_count = 0
    for idx, pair in selected:
        is_correct = submitted.get(str(idx)) == pair["technique"]
        per_slot[str(idx)] = is_correct
        if is_correct:
            correct_count += 1

    if correct_count == len(selected):
        return True, f"All {len(selected)} matches correct!", {
            "slot_results": per_slot,
            "last_match": submitted,
        }

    detail = (
        f"{correct_count} out of {len(selected)} correct. "
        "Highlighted rows show which need adjusting."
    )
    return False, detail, {"slot_results": per_slot, "last_match": submitted}


@register_grader("order_match")
def grade_order_match(activity, team, payload):
    """
    Check that the student's submitted line order matches the correct order
    (index 0, 1, 2, … n-1 = the lines as given in config["lines"]).
    payload is a JSON string like "[2, 0, 3, 1]".
    """
    import json as _json
    config = resolve_config(activity, team)
    lines = config.get("lines", [])
    correct = list(range(len(lines)))

    try:
        submitted = _json.loads(payload) if isinstance(payload, str) else list(payload)
    except (ValueError, TypeError):
        submitted = []

    if not isinstance(submitted, list) or len(submitted) != len(correct):
        return False, "Submission format error — please try again.", {}

    # Compare text content, not indices, so duplicate lines are interchangeable.
    try:
        submitted_text = [lines[i] for i in submitted]
    except (IndexError, TypeError):
        return False, "Submission format error — please try again.", {}

    if submitted_text == lines:
        return True, "Correct! The steps are in the right order.", {}

    return False, "Not quite — keep rearranging and try again.", {}
