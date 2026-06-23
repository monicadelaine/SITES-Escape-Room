"""
python manage.py export_packets <slug> [--output-dir ./packets]

Generates one printable HTML sheet per team per activity.

Layout (portrait letter):
  ┌─────────────────────────────┐
  │  TOP 1/3 — team name +      │  ← stays visible when sheet is folded
  │            door title +      │
  │            LOGIN PASSWORD    │
  ├ ─ ─ ─ ─ fold here ─ ─ ─ ─ ┤
  │  CS/AI/Cybersecurity context │
  │  Activity instructions       │
  └─────────────────────────────┘

Output files:  packets/<TeamName>-door-<N>.html
Open in a browser and use File → Print (or Cmd/Ctrl+P).
"""
import json as _json
import textwrap
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


# ── CS / AI / Cybersecurity connection descriptions ───────────────────────────

CS_CONNECTIONS = {
    "test_case_runner": {
        "label": "Computer Science — Algorithms & Programming",
        "body": (
            "<p>Writing loops and conditionals is the foundation of every program ever built "
            "— from mobile apps to AI models running on supercomputers. Finding the largest "
            "or smallest value in a list is a classic <em>linear search</em> problem. "
            "Computer scientists measure algorithm efficiency using <em>Big-O notation</em>: "
            "this approach is <strong>O(n)</strong>, meaning it takes one pass through the "
            "data regardless of what the values are. That makes it both simple and optimal — "
            "you cannot find the answer without looking at every element at least once.</p>"
            "<p>Every search engine, recommendation system, and AI training loop runs "
            "variations of this same idea billions of times per second.</p>"
        ),
    },
    "decode_compare": {
        "label": "Cybersecurity — Cryptography &amp; Encryption",
        "body": (
            "<p>The Caesar cipher is one of the earliest encryption algorithms on record, "
            "used by Julius Caesar around 50 BCE to protect military orders. It works by "
            "<em>shifting</em> every letter a fixed number of places in the alphabet — "
            "simple, but breakable with only 25 guesses. That is a <em>brute-force attack</em>.</p>"
            "<p>Modern encryption (AES-256, RSA, elliptic-curve) applies the same idea — "
            "transform data so only authorized parties can read it — but with keys so large "
            "that brute-forcing them would take longer than the age of the universe. "
            "Cybersecurity professionals study cryptography to protect everything from "
            "banking transactions to government secrets. A small math mistake can expose "
            "millions of people's data.</p>"
        ),
    },
    "secret_match": {
        "label": "AI &amp; Cybersecurity — Prompt Injection",
        "body": (
            "<p><em>Large Language Models</em> (LLMs) — the technology behind ChatGPT, "
            "Gemini, and Claude — are trained to follow instructions embedded in a "
            "<em>system prompt</em> that users normally cannot see. <em>Prompt injection</em> "
            "is a real attack technique where a user crafts a message that tricks the AI "
            "into ignoring those hidden instructions and doing something it was told not to.</p>"
            "<p>This is an active research area at every major AI lab. Engineers who deploy "
            "AI systems spend considerable effort on <em>prompt hardening</em> — designing "
            "system prompts that resist manipulation. AI safety researchers study these "
            "vulnerabilities to understand how to build more reliable, trustworthy systems. "
            "If you're interested in AI or cybersecurity, this intersection is one of the "
            "fastest-growing career fields in tech.</p>"
        ),
    },
    "match_grader": {
        "label": "Cybersecurity — Social Engineering &amp; Human Factors",
        "body": (
            "<p>Technical defenses — firewalls, encryption, antivirus software — only "
            "protect against technical attacks. <em>Social engineering</em> bypasses "
            "technology entirely by exploiting human psychology: urgency, authority, "
            "curiosity, and trust. Studies consistently show that <strong>80–95% of "
            "successful cyberattacks</strong> involve a human being tricked rather than "
            "a system being hacked.</p>"
            "<p>Cybersecurity professionals must understand not just code but also "
            "behavior — the \"wetware\" is often the weakest link. Recognizing these "
            "techniques in real life (phishing emails, fake IT calls, suspicious links) "
            "is one of the most practical skills a computer science or cybersecurity "
            "student can develop.</p>"
        ),
    },
    "order_match": {
        "label": "Computer Science — Algorithm Design &amp; Robotics",
        "body": (
            "<p>An <em>algorithm</em> is a precise, ordered sequence of instructions "
            "for solving a problem — the most fundamental concept in computer science. "
            "Order matters: swap two steps and the result is completely wrong. This is "
            "exactly how robots, 3D printers, CNC machines, and autonomous vehicles "
            "work: translating a high-level goal (\"draw a triangle\", \"pick up this "
            "object\") into an exact sequence of low-level actions.</p>"
            "<p>AI planning systems face this same challenge — given a goal, determine "
            "the correct sequence of actions. Turtle graphics were invented in the 1960s "
            "by Seymour Papert at MIT as a tool to teach this kind of algorithmic "
            "thinking, and they remain one of the clearest ways to see computation in "
            "action. The same ideas underlie modern robot motion planning and game AI.</p>"
        ),
    },
    "manual_staff": {
        "label": "Computer Science — Human-in-the-Loop Systems",
        "body": (
            "<p>Not everything should be automated. In safety-critical systems — "
            "medical devices, air-traffic control, nuclear power plants, large financial "
            "transactions — a <em>human-in-the-loop</em> check is required even when "
            "full automation is technically possible. The human provides judgment, "
            "accountability, and a check against edge cases the system was not designed for.</p>"
            "<p>This is an active design consideration in AI systems today: when should "
            "an AI act autonomously, and when should it pause and ask a human? Getting "
            "that balance right is one of the central questions of responsible AI "
            "development and a key topic in both AI and cybersecurity degrees.</p>"
        ),
    },
}


# ── prose blocks ─────────────────────────────────────────────────────────────

CIPHER_EXPLAINER_PARAS = [
    (
        "This message was encoded with a <em>Caesar cipher</em> — one of the oldest "
        "encryption methods, famously used by Julius Caesar to send secret military orders. "
        "Every letter in the original message was shifted a fixed number of places forward "
        "in the alphabet, wrapping from Z back to A."
    ),
    (
        "For example, with a shift of 3: A→D, B→E, C→F, … Z→C. "
        "To decode the message you need to find the shift that was used and reverse it. "
        "You can guess and check, or — more reliably — try all 26 possibilities until "
        "the message becomes readable English. "
        "That second approach is called a <em>brute-force attack</em>, and it is exactly "
        "what real attackers do against weak encryption."
    ),
    (
        "Enter your shift guess on the web page. Each time you try a shift you will see "
        "what the message decodes to, so you can keep adjusting."
    ),
]

LLM_TIPS_HTML = """\
<p>The AI guardian is hiding a secret code. Your job is to trick it into revealing the
code — this is called <em>prompt injection</em>.</p>
<p><strong>Approaches to try:</strong></p>
<ul>
  <li>Ask it to repeat its instructions back to you.</li>
  <li>Ask it to write a poem or story that contains the code.</li>
  <li>Claim you are the developer running a security test.</li>
  <li>Ask it to "translate" or reformat the code into another form.</li>
  <li>Try to get it to roleplay as a character with no restrictions.</li>
</ul>
<p>When you find the code, enter it in the <strong>Enter the Secret</strong> field
on the web page — not in the chat box.</p>
"""


# ── HTML shell ───────────────────────────────────────────────────────────────

PAGE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{team_name} · Door {order} · {title}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@400;600&display=swap');

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  html, body {{
    width:  8.5in;
    height: 11in;
    overflow: hidden;
    background: #fff;
    color: #1c1e24;
    font-family: 'IBM Plex Sans', sans-serif;
  }}

  .sheet {{
    width:  8.5in;
    height: 11in;
    display: flex;
    flex-direction: column;
  }}

  /* ---- top third: visible after folding ---- */
  .cover {{
    flex: 0 0 calc(11in / 3);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 0.3in 0.7in;
    background: {cover_bg};
    border-bottom: none;
  }}

  .cover-event {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5pt;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: {cover_dim};
    margin-bottom: 0.1in;
  }}

  .cover-team {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 34pt;
    font-weight: 700;
    color: {cover_text};
    line-height: 1.1;
    margin-bottom: 0.08in;
  }}

  .cover-door {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13pt;
    font-weight: 600;
    color: {cover_accent};
    margin-bottom: 0.04in;
  }}

  .cover-title {{
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 11.5pt;
    color: {cover_dim};
    margin-bottom: 0.14in;
  }}

  .cover-password-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 8pt;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: {cover_dim};
    margin-bottom: 0.04in;
  }}

  .cover-password {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 20pt;
    font-weight: 700;
    color: {cover_text};
    background: rgba(255,255,255,0.08);
    border: 1.5px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 0.05in 0.25in;
    letter-spacing: .08em;
  }}

  /* ---- fold indicator ---- */
  .fold-rule {{
    flex: 0 0 0;
    border-top: 1.5px dashed {fold_color};
    position: relative;
  }}
  .fold-rule::before {{
    content: "— fold here —";
    position: absolute;
    top: -0.12in;
    left: 50%;
    transform: translateX(-50%);
    background: #fff;
    padding: 0 0.1in;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 7pt;
    letter-spacing: .06em;
    text-transform: uppercase;
    color: {fold_color};
  }}

  /* ---- bottom two-thirds: instructions ---- */
  .content {{
    flex: 1 1 0;
    padding: 0.38in 0.7in 0.3in;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 0.13in;
  }}

  .content-header {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13pt;
    font-weight: 700;
    color: #12141a;
    border-left: 5px solid {accent};
    padding-left: 0.12in;
    margin-bottom: 0.02in;
  }}

  .cs-connection {{
    background: #f0f4ff;
    border-left: 4px solid {accent};
    border-radius: 0 6px 6px 0;
    padding: 0.1in 0.14in;
  }}

  .cs-connection-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: {accent};
    margin-bottom: 0.05in;
  }}

  .cs-connection p {{
    font-size: 9.5pt;
    line-height: 1.5;
    color: #2b2d34;
    margin-bottom: 0.05in;
  }}
  .cs-connection p:last-child {{ margin-bottom: 0; }}

  .activity-section {{
    display: flex;
    flex-direction: column;
    gap: 0.08in;
  }}

  .activity-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #6b6f7b;
  }}

  p, li {{
    font-size: 10.5pt;
    line-height: 1.5;
    color: #2b2d34;
  }}

  ul {{
    padding-left: 1.2em;
    margin: 0.04in 0;
  }}
  li {{ margin-bottom: 0.03in; }}

  pre, .cipher-box {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10.5pt;
    background: #f7f5ee;
    border: 1.5px solid #ece9e1;
    border-radius: 6px;
    padding: 0.12in 0.14in;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.6;
  }}

  .blank-line {{
    display: inline-block;
    min-width: 1.5in;
    border-bottom: 2px solid #c98a12;
    color: #c98a12;
    font-style: italic;
    padding-bottom: 1px;
  }}

  .cipher-box {{
    font-size: 12.5pt;
    letter-spacing: .05em;
    color: #c0392b;
    background: #fff8f8;
    border-color: #fecdcd;
    margin: 0.04in 0;
  }}

  .hint {{
    font-size: 10pt;
    color: #6b6f7b;
    margin: 0;
  }}
  .hint strong {{ color: #1c1e24; }}

  .explainer {{
    background: #f3f1ea;
    border-left: 4px solid #dedad3;
    border-radius: 0 6px 6px 0;
    padding: 0.1in 0.13in;
    font-size: 9.5pt;
    color: #4b4f5b;
    line-height: 1.5;
  }}
  .explainer p {{ margin-bottom: 0.06in; }}
  .explainer p:last-child {{ margin-bottom: 0; }}

  .staff-note {{
    font-size: 10pt;
    color: #9a9eac;
    font-style: italic;
    border-left: 3px solid #dedad3;
    padding-left: 0.1in;
    margin-top: 0.06in;
  }}

  /* ── technique reference table (match_pairs) ── */
  .technique-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
    margin: 0.04in 0 0.06in;
  }}
  .technique-table th {{
    background: #1c1e24;
    color: #e9e7e1;
    text-align: left;
    padding: 3px 7px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 8.5pt;
    letter-spacing: .04em;
  }}
  .technique-table td {{
    padding: 3px 7px;
    border-bottom: 1px solid #e5e3db;
    color: #2b2d34;
    vertical-align: top;
  }}
  .technique-table tr:nth-child(even) td {{ background: #f7f5ee; }}
  .technique-table td:first-child {{
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    white-space: nowrap;
    color: {accent};
    width: 1.55in;
  }}

  /* ── scenarios list (match_pairs) ── */
  .scenario-list {{
    list-style: none;
    padding: 0;
    margin: 0.04in 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }}
  .scenario-list li {{
    font-size: 9.5pt;
    background: #f7f5ee;
    border: 1.5px solid #ece9e1;
    border-radius: 5px;
    padding: 4px 9px;
    color: #1c1e24;
    font-style: italic;
  }}

  /* ── scrambled pseudocode lines (pseudocode_order) ── */
  .scrambled-lines {{
    list-style: none;
    padding: 0;
    margin: 0.04in 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }}
  .scrambled-lines li {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10pt;
    background: #f7f5ee;
    border: 1.5px solid #ece9e1;
    border-radius: 5px;
    padding: 4px 9px;
    color: #1c1e24;
  }}

  @media print {{
    html, body {{ width: 8.5in; height: 11in; }}
    .sheet {{ page-break-after: always; }}
    @page {{ size: letter portrait; margin: 0; }}
  }}
</style>
</head>
<body>
<div class="sheet">

  <!-- TOP 1/3 — visible when folded -->
  <div class="cover">
    <div class="cover-event">{session_name}</div>
    <div class="cover-team">{team_name}</div>
    <div class="cover-door">Door {order}</div>
    <div class="cover-title">{title}</div>
    {password_html}
  </div>

  <!-- fold line -->
  <div class="fold-rule"></div>

  <!-- BOTTOM 2/3 — fold inward to hide -->
  <div class="content">
    <div class="content-header">{title}</div>
    {cs_block_html}
    <div class="activity-section">
      <div class="activity-label">Your Task</div>
{body_html}
    </div>
  </div>

</div>
</body>
</html>
"""

# Per-door accent/cover colours  (cycles via modulo for doors > 7)
_THEME_PALETTE = [
    {"accent": "#f5b942", "cover_text": "#f5b942"},  # 1 amber
    {"accent": "#ef6a6a", "cover_text": "#ef6a6a"},  # 2 rose
    {"accent": "#a78bfa", "cover_text": "#a78bfa"},  # 3 violet
    {"accent": "#2bd9c8", "cover_text": "#2bd9c8"},  # 4 teal
    {"accent": "#fb923c", "cover_text": "#fb923c"},  # 5 orange
    {"accent": "#4ade80", "cover_text": "#4ade80"},  # 6 green
    {"accent": "#60a5fa", "cover_text": "#60a5fa"},  # 7 blue
]
_THEME_BASE = {
    "cover_bg":    "#0e1015",
    "cover_dim":   "#9a9eac",
    "cover_accent": "#e9e7e1",
    "fold_color":  "#3a3d48",
}

def _theme(order):
    palette = _THEME_PALETTE[(order - 1) % len(_THEME_PALETTE)]
    return {**_THEME_BASE, **palette}

# Keep DOOR_THEMES for backwards compat in case anything imports it
DOOR_THEMES = {i + 1: {**_THEME_BASE, **p} for i, p in enumerate(_THEME_PALETTE)}


# ── helpers ───────────────────────────────────────────────────────────────────

def _h(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cs_block(grader_type, accent):
    info = CS_CONNECTIONS.get(grader_type)
    if not info:
        return ""
    return (
        f'<div class="cs-connection">'
        f'<div class="cs-connection-label">{info["label"]}</div>'
        f'{info["body"]}'
        f'</div>'
    )


# ── per-activity body HTML builders ──────────────────────────────────────────

def _body_blank_fill(cfg):
    template = cfg.get("template", "")
    parts = template.split("___BLANK___", 1)
    before = _h(parts[0]) if parts else ""
    after  = _h(parts[1]) if len(parts) > 1 else ""
    return (
        '      <p>Complete the program by filling in the missing line:</p>\n'
        f'      <pre>{before}<span class="blank-line">_______________</span>{after}</pre>\n'
        '      <p>Your solution must work correctly for several different random number lists. '
        'Enter the missing line on the web page to test it.</p>'
    )


def _body_decode_compare(cfg):
    from escaperoom.graders import caesar_encode
    plaintext  = cfg.get("plaintext", "")
    shift      = cfg.get("shift", 0)
    ciphertext = caesar_encode(plaintext, shift)
    first_word = plaintext.split()[0] if cfg.get("first_word_hint") and plaintext else None

    hint_html = (
        f'      <p class="hint">First word decodes to: <strong>{_h(first_word)}</strong></p>\n'
        if first_word else ""
    )
    explainer_paras = "".join(f"<p>{p}</p>" for p in CIPHER_EXPLAINER_PARAS)

    return (
        '      <p>Decode this message:</p>\n'
        f'      <div class="cipher-box">{_h(ciphertext)}</div>\n'
        f'{hint_html}'
        f'      <div class="explainer">{explainer_paras}</div>'
    )


def _body_secret_match():
    return f'      {LLM_TIPS_HTML.strip()}'


def _body_manual_staff(cfg):
    instructions = cfg.get("instructions", "")
    return (
        f'      <p>{_h(instructions)}</p>\n'
        '      <p class="staff-note">Nothing to submit on the web — '
        'a staff member will mark this door complete once they see you finish.</p>'
    )


def _body_match_pairs(cfg, team, act):
    """Show the technique reference table + this team's specific 5 scenarios."""
    from escaperoom.graders import _get_team_pairs
    technique_descriptions = cfg.get("technique_descriptions", [])

    # Build technique reference table
    if technique_descriptions:
        rows = "".join(
            f'<tr><td>{_h(td["name"])}</td><td>{_h(td["description"])}</td></tr>'
            for td in technique_descriptions
        )
        table_html = (
            '      <p><strong>Social Engineering Techniques — Reference</strong></p>\n'
            '      <table class="technique-table">\n'
            '        <thead><tr><th>Technique</th><th>What it exploits</th></tr></thead>\n'
            f'        <tbody>{rows}</tbody>\n'
            '      </table>\n'
        )
    else:
        table_html = ""

    # Show this team's specific scenarios (deterministic selection)
    if team and act:
        selected = _get_team_pairs(cfg, team, act)
        scenario_items = "".join(
            f'<li>"{_h(pair["scenario"])}"</li>'
            for _, pair in selected
        )
        scenarios_html = (
            '      <p><strong>Your 5 scenarios to match:</strong></p>\n'
            f'      <ul class="scenario-list">{scenario_items}</ul>\n'
        )
    else:
        pairs = cfg.get("pairs", [])
        scenario_items = "".join(f'<li>"{_h(p["scenario"])}"</li>' for p in pairs)
        scenarios_html = (
            '      <p><strong>Scenarios to match:</strong></p>\n'
            f'      <ul class="scenario-list">{scenario_items}</ul>\n'
        )

    instructions = (
        '      <p>On the web page, drag each technique label onto the scenario it describes. '
        'Use the reference table above to help you decide.</p>'
    )

    return table_html + scenarios_html + instructions


def _body_pseudocode_order(cfg, team, act):
    """Show per-team scrambled lines (same seed as the web UI)."""
    import random as _random
    lines       = cfg.get("lines", [])
    description = cfg.get("description", "")
    image_file  = cfg.get("image_file", "")

    # Match the same shuffle seed used by the web UI
    team_pk = team.pk if team else 0
    act_pk  = act.pk  if act  else 0
    rng = _random.Random(team_pk * 7919 + act_pk)
    indices = list(range(len(lines)))
    rng.shuffle(indices)
    scrambled = [lines[i] for i in indices]

    desc_html = f'      <p>{_h(description)}</p>\n' if description else ""
    img_note  = (
        '      <p><em>(See the image on the web page for the target figure.)</em></p>\n'
        if image_file else ""
    )
    items = "".join(f'<li>{_h(line)}</li>' for line in scrambled)
    lines_html = (
        '      <p>The steps below are scrambled. On the web page, drag them into the correct order:</p>\n'
        f'      <ul class="scrambled-lines">{items}</ul>\n'
    )

    return desc_html + img_note + lines_html


def _build_body(grader_type, cfg, team=None, act=None):
    if grader_type == "test_case_runner":
        return _body_blank_fill(cfg)
    elif grader_type == "decode_compare":
        return _body_decode_compare(cfg)
    elif grader_type == "secret_match":
        return _body_secret_match()
    elif grader_type == "manual_staff":
        return _body_manual_staff(cfg)
    elif grader_type == "match_grader":
        return _body_match_pairs(cfg, team, act)
    elif grader_type == "order_match":
        return _body_pseudocode_order(cfg, team, act)
    return "      <p>(No instructions defined.)</p>"


# ── command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Export one printable HTML sheet per team per activity."

    def add_arguments(self, parser):
        parser.add_argument("slug", type=str)
        parser.add_argument("--output-dir", type=str, default="./packets")

    def handle(self, *args, **options):
        from escaperoom.models import Activity, Session, Team, TeamActivityProgress

        slug = options["slug"]
        try:
            session = Session.objects.get(slug=slug)
        except Session.DoesNotExist:
            raise CommandError(f"Session '{slug}' not found.")

        # Try to load plain-text passwords from sessions/<slug>.json
        password_map = {}
        json_candidates = [
            Path(f"sessions/{slug}.json"),
            Path(f"sessions/{slug.lower()}.json"),
            Path(f"sessions/{slug.upper()}.json"),
        ]
        for candidate in json_candidates:
            if candidate.exists():
                try:
                    with open(candidate, encoding="utf-8") as f:
                        data = _json.load(f)
                    password_map = {t["name"]: t["password"] for t in data.get("teams", [])}
                    self.stdout.write(f"  Passwords loaded from {candidate}")
                except Exception:
                    pass
                break

        out_dir = Path(options["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)

        teams      = list(Team.objects.filter(session=session).order_by("name"))
        activities = list(Activity.objects.filter(session=session).order_by("order"))

        if not teams:
            raise CommandError("No teams found for this session.")

        count = 0
        for team in teams:
            for act in activities:
                try:
                    progress = TeamActivityProgress.objects.get(team=team, activity=act)
                    cfg = {**act.config, **progress.config_override}
                except TeamActivityProgress.DoesNotExist:
                    cfg = act.config

                theme    = _theme(act.order)
                body     = _build_body(act.grader_type, cfg, team=team, act=act)
                cs_block = _cs_block(act.grader_type, theme["accent"])

                # Password block for cover
                plain_pw = password_map.get(team.name, "")
                if plain_pw:
                    password_html = (
                        '<div class="cover-password-label">Login Password</div>'
                        f'<div class="cover-password">{_h(plain_pw)}</div>'
                    )
                else:
                    password_html = ""

                html = PAGE_HTML.format(
                    session_name  = _h(session.name),
                    team_name     = _h(team.name),
                    order         = act.order,
                    title         = _h(act.title),
                    password_html = password_html,
                    cs_block_html = cs_block,
                    body_html     = body,
                    **theme,
                )

                safe = team.name.replace(" ", "_")
                out_path = out_dir / f"{safe}-door-{act.order}.html"
                out_path.write_text(html, encoding="utf-8")
                self.stdout.write(f"  {out_path}")
                count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n{count} sheet(s) written to {out_dir}/ "
            f"({len(teams)} team(s) × {len(activities)} door(s)).\n"
            "Open any file in a browser and use File → Print."
        ))
