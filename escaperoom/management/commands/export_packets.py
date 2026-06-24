"""
python manage.py export_packets <slug> [--output-dir ./packets]

Generates one printable HTML sheet per team per activity.

Layout (portrait letter):
  ┌─────────────────────────────┐
  │  TOP 1/3 — team name +      │  ← stays visible when sheet is folded
  │            gate title +      │
  │            LOGIN PASSWORD    │
  ├ ─ ─ ─ ─ fold here ─ ─ ─ ─ ┤
  │  CS/AI/Cybersecurity context │
  │  Activity instructions       │
  └─────────────────────────────┘

Output files:  packets/<TeamName>-gate-<N>.html
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
<title>{team_name} · Gate {order} · {title}</title>
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
    background: rgba(0,0,0,0.04);
    border: 1.5px solid rgba(0,0,0,0.12);
    border-radius: 8px;
    padding: 0.05in 0.25in;
    letter-spacing: .08em;
  }}

  .cover-url-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 7.5pt;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: {cover_dim};
    margin-top: 0.1in;
    margin-bottom: 0.03in;
  }}

  .cover-url {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11pt;
    font-weight: 600;
    color: {cover_text};
    letter-spacing: .02em;
  }}

  .cover-logo {{
    margin-top: 0.12in;
    opacity: 0.85;
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
    <svg width="52" height="44" viewBox="0 0 52 44" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-bottom:0.06in; color:{cover_text};">
      <rect x="3" y="17" width="7" height="27" rx="2" fill="currentColor"/>
      <rect x="42" y="17" width="7" height="27" rx="2" fill="currentColor"/>
      <path d="M3 21 Q3 3 26 3 Q49 3 49 21" stroke="currentColor" stroke-width="5" fill="none" stroke-linecap="round"/>
      <rect x="0.5" y="14" width="13" height="5" rx="1.5" fill="currentColor"/>
      <rect x="38.5" y="14" width="13" height="5" rx="1.5" fill="currentColor"/>
    </svg>
    <div class="cover-team">{team_name}</div>
    <div class="cover-door">Gate {order}</div>
    <div class="cover-title">{title}</div>
    {password_html}
    {url_html}
    <div class="cover-logo">
      <svg width="180" height="10" viewBox="0 0 333 18" fill="none" xmlns="http://www.w3.org/2000/svg">
        <g fill="#9E1B32">
          <path d="M4.815 17.479C5.30062 16.3865 5.49692 15.1874 5.385 13.997V1.74701H1.9C1.2064 1.70313 0.523542 1.93495 0 2.39201L0.507 0.458008H13.749C13.305 1.61901 11.723 1.81201 10.649 1.81201H7.73V14.062C7.61263 15.2522 7.80916 16.4524 8.3 17.543L4.815 17.479Z"/>
          <path d="M26.1 3.93901C26.1804 2.74447 25.964 1.5486 25.47 0.458008H29.082C28.5923 1.55 28.3747 2.74448 28.448 3.93901V13.996C28.3688 15.1909 28.5866 16.3868 29.082 17.477H25.534C26.0237 16.385 26.2413 15.1905 26.168 13.996V8.83901H18.311V13.997C18.2318 15.1919 18.4496 16.3878 18.945 17.478H15.4C15.8897 16.386 16.1073 15.1915 16.034 13.997V3.93901C16.1133 2.74413 15.8955 1.54821 15.4 0.458008H18.948C18.4583 1.55 18.2407 2.74448 18.314 3.93901V7.73901H26.1V3.93901Z"/>
          <path d="M34.847 16.446H37.888C39.5498 16.5271 41.1803 15.9742 42.45 14.899L41.943 17.349C41.243 17.413 40.359 17.478 39.409 17.478H31.809C32.3159 16.3914 32.5342 15.1925 32.443 13.997V3.93901C32.5594 2.74854 32.3619 1.54834 31.87 0.458008H41.057L41.184 2.52101C40.0406 1.77438 38.6793 1.43381 37.319 1.55401H34.847V7.93601C36.873 7.93601 38.964 7.93601 41.055 7.74301C40.105 9.29001 37.19 9.29001 35.543 9.29001H34.91V16.446H34.847Z"/>
          <path d="M65.623 0.456998C65.1375 1.57251 64.9414 2.79253 65.053 4.004V14.066C64.9355 15.2569 65.132 16.4577 65.623 17.549L62.455 17.678L62.582 15.937C62.5802 15.9039 62.5663 15.8726 62.543 15.849C62.5196 15.8252 62.4883 15.8106 62.455 15.808C62.39 15.808 62.328 15.937 62.138 16.131C60.7292 17.3453 58.9289 18.0094 57.069 18.001C54.028 18.001 52 16.711 51.937 13.422V3.94C52.0475 2.72787 51.8501 1.50746 51.363 0.391998H54.848C54.3625 1.50751 54.1664 2.72753 54.278 3.939V11.739C54.343 14.577 55.545 16.318 58.46 16.318C61.375 16.318 62.451 14.383 62.515 11.158C62.515 10.126 62.642 9.094 62.642 8.058V3.94C62.7544 2.72837 62.559 1.50799 62.074 0.391998L65.623 0.456998Z"/>
          <path d="M66.813 17.48C67.763 15.288 67.763 11.999 67.763 9.68001V4.00401C67.763 2.71401 67.698 1.23101 66.94 0.458008H69.601C70.108 0.458008 70.361 0.458008 70.678 0.909008C71.248 1.68301 72.896 4.52001 73.719 5.68001L78.977 13.224C79.167 13.482 79.357 13.869 79.548 13.869C79.739 13.869 79.738 13.611 79.738 13.353V3.87201C79.8168 2.69882 79.5987 1.5247 79.104 0.458008H81.828C81.2603 1.71198 80.9998 3.08322 81.068 4.45801V15.158C81.068 16.058 81.068 16.834 81.133 17.673H79.233L69.537 3.68201C69.41 3.55301 69.347 3.42401 69.22 3.42401C69.093 3.42401 69.093 3.55301 69.093 3.81101V10.711C69.093 12.839 69.028 15.547 69.853 17.546L66.813 17.48Z"/>
          <path d="M85.126 3.93901C85.244 2.74898 85.0482 1.54879 84.558 0.458008H88.106C87.6205 1.55022 87.4242 2.74899 87.536 3.93901V13.996C87.4186 15.1862 87.6152 16.3864 88.106 17.477H84.558C85.0438 16.3849 85.2405 15.1861 85.129 13.996L85.126 3.93901Z"/>
          <path d="M95.162 17.609L94.782 16.255C93.515 12 91.682 5.423 89.84 1.361L89.397 0.460999H91.741C92.248 0.460999 92.375 1.106 92.501 1.493C93.895 5.619 95.415 9.746 96.492 14.001C96.619 14.517 96.746 14.775 96.936 14.775C97.126 14.775 97.253 14.324 97.38 13.937C98.14 11.616 101.372 3.943 101.372 1.429C101.361 1.10334 101.318 0.779519 101.245 0.461999H104.476L103.97 1.3C101.505 6.09894 99.4085 11.0779 97.697 16.194L97.19 17.613H95.162V17.609Z"/>
          <path d="M108.409 16.446H111.451C113.113 16.527 114.743 15.9741 116.013 14.899L115.505 17.349C114.805 17.413 113.921 17.478 112.971 17.478H105.371C105.878 16.3915 106.096 15.1926 106.005 13.997V3.93901C106.122 2.74881 105.926 1.54869 105.435 0.458008H114.622L114.748 2.52101C113.608 1.76666 112.245 1.42539 110.884 1.55401H108.472V7.93601C110.498 7.93601 112.655 7.93601 114.68 7.74301C113.794 9.29001 110.816 9.29001 109.168 9.29001H108.535L108.409 16.446Z"/>
          <path d="M129.022 15.028C129.674 15.9393 130.417 16.7819 131.239 17.543H129.083C127.943 17.543 127.435 16.898 126.866 16.06L123.634 11.417C122.557 9.80499 122.367 9.35399 120.846 9.22499V14.061C120.729 15.2516 120.925 16.4522 121.417 17.543H117.744C118.334 16.4132 118.577 15.1345 118.444 13.867V3.93699C118.561 2.74636 118.364 1.54577 117.873 0.454991C120.09 0.454991 122.182 0.196991 124.212 0.196991C126.873 0.196991 128.267 1.67999 128.267 3.80799C128.267 6.25799 126.302 7.87099 124.402 8.64399L129.022 15.028ZM120.849 8.12799C121.246 8.18295 121.648 8.20436 122.049 8.19199C122.58 8.25144 123.117 8.19052 123.621 8.01375C124.125 7.83698 124.583 7.5489 124.96 7.17093C125.338 6.79295 125.625 6.33479 125.801 5.83049C125.977 5.32619 126.037 4.78871 125.977 4.25799C125.977 1.54999 124.456 1.22699 122.112 1.22699H120.845C120.845 1.61399 120.78 2.06499 120.78 2.51699L120.849 8.12799Z"/>
          <path d="M131.147 14.192C131.606 15.0288 132.286 15.7237 133.113 16.2013C133.939 16.6789 134.881 16.9209 135.835 16.901C136.293 16.9336 136.754 16.8699 137.186 16.714C137.617 16.5589 138.011 16.3145 138.341 15.997C138.67 15.6811 138.927 15.299 139.097 14.876C139.265 14.454 139.342 14.0009 139.32 13.547C139.32 9.03101 131.78 9.61201 131.78 4.64701C131.78 1.48601 134.251 0.00201416 137.102 0.00201416C138.496 0.00201416 139.827 0.131014 141.157 0.131014V2.64501C140.734 2.08711 140.175 1.64679 139.534 1.36601C138.89 1.08361 138.185 0.969037 137.485 1.03301C135.648 1.03301 134.254 2.00101 134.254 4.00001C134.254 8.12901 141.794 7.61301 141.794 12.709C141.794 15.999 138.626 17.87 135.651 17.87C134.106 17.8095 132.584 17.482 131.151 16.902L131.147 14.192Z"/>
          <path d="M145.209 3.93901C145.326 2.74881 145.13 1.54869 144.639 0.458008H148.187C147.702 1.55029 147.505 2.749 147.617 3.93901V13.996C147.5 15.1862 147.696 16.3863 148.187 17.477H144.639C145.124 16.3847 145.321 15.186 145.209 13.996V3.93901Z"/>
          <path d="M154.653 17.478C155.138 16.3854 155.335 15.1863 155.223 13.996V1.746H151.738C151.056 1.70961 150.383 1.91501 149.838 2.326L150.344 0.391998H163.586C163.142 1.553 161.56 1.746 160.486 1.746H157.571V13.996C157.454 15.1866 157.65 16.3872 158.142 17.478H154.653Z"/>
          <path d="M167.916 17.478C168.401 16.3854 168.598 15.1863 168.486 13.996V11.546C168.486 9.67599 167.726 7.87099 166.649 5.67899C165.783 3.73878 164.606 1.95297 163.164 0.391991H165.444C166.394 0.391991 166.585 0.649991 167.028 1.42399C168.21 3.49226 169.126 5.70181 169.753 7.99999C169.879 8.38699 169.943 8.77399 170.196 8.77399C170.449 8.77399 170.513 8.32299 170.83 7.87399L172.604 4.64999C173.215 3.68971 173.623 2.61473 173.804 1.49099C173.804 1.09205 173.671 0.704572 173.424 0.390991H176.724L173.747 5.16199C171.909 7.99899 170.896 9.35299 170.896 12.899V13.999C170.779 15.1895 170.975 16.39 171.466 17.481L167.916 17.478Z"/>
          <path d="M191.209 17.935C185.697 17.935 183.289 14.064 183.289 9.29C183.289 4.258 186.203 0 191.653 0C197.103 0 199.573 3.871 199.573 8.645C199.636 13.677 196.721 17.935 191.209 17.935ZM191.463 1.161C187.663 1.161 186.077 4.709 186.077 8.516C186.077 12.064 187.277 16.709 191.463 16.709C195.263 16.709 196.848 13.161 196.848 9.354C196.848 5.806 195.708 1.161 191.463 1.161Z"/>
          <path d="M204.525 13.996C204.408 15.1862 204.604 16.3863 205.095 17.477H201.547C202.032 16.3847 202.229 15.186 202.117 13.996V3.93901C202.255 2.75431 202.08 1.55409 201.61 0.458008H209.781C210.415 0.458008 210.981 0.458008 210.981 0.716008V2.77901H210.855C210.095 1.55401 208.447 1.49001 207.243 1.49001H204.519V8.39001C206.544 8.39001 208.635 8.39001 210.727 8.19701C209.779 9.74201 206.869 9.74201 205.218 9.74201H204.584L204.525 13.996Z"/>
          <path d="M231.569 17.478L228.718 10H222.762C221.622 12.321 220.481 14.964 220.481 16.447C220.471 16.7923 220.494 17.1377 220.547 17.479H217.247L217.817 16.77C219.338 14.836 224.723 3.36001 224.723 1.17001V0.458008H227.828C229.475 5.80901 231.186 11.611 233.845 16.511L234.352 17.478H231.569ZM226.374 3.23001C226.308 3.03701 226.184 2.58501 225.93 2.58501C225.676 2.58501 225.55 3.10101 225.486 3.23001L223.205 8.97201H228.205L226.374 3.23001Z"/>
          <path d="M236.344 3.93901C236.461 2.74881 236.265 1.54869 235.774 0.458008H239.322C238.837 1.55029 238.64 2.749 238.752 3.93901V16.446H240.716C241.475 16.5041 242.237 16.3956 242.95 16.128C243.66 15.8616 244.303 15.442 244.833 14.899L244.326 17.413C243.8 17.4668 243.271 17.4885 242.742 17.478H235.457C236.218 16.446 236.344 12.643 236.344 11.418V3.93901Z"/>
          <path d="M259.151 17.478L256.3 10H250.351C249.211 12.321 248.007 14.964 248.007 16.447C247.997 16.7923 248.019 17.1377 248.072 17.479H244.772L245.342 16.77C246.863 14.836 252.248 3.36001 252.248 1.17001V0.458008H255.348C257.058 5.80901 258.706 11.611 261.365 16.511L261.872 17.478H259.151ZM253.951 3.23001C253.885 3.03701 253.761 2.58501 253.507 2.58501C253.253 2.58501 253.127 3.10101 253.063 3.23001L250.793 8.97201H255.793L253.951 3.23001Z"/>
          <path d="M262.828 3.93701C262.947 2.74651 262.751 1.54572 262.262 0.454014C264.542 0.454014 266.95 0.196014 269.231 0.196014C271.257 0.196014 273.159 1.09601 273.159 3.42101C273.159 5.74601 271.321 6.90401 269.484 7.67701V7.74201C271.954 8.32201 274.046 9.29001 274.046 12.192C274.046 16.384 270.878 17.674 267.33 17.674C265.556 17.674 263.782 17.545 262.008 17.545C262.895 15.675 262.895 12.902 262.895 10.838L262.828 3.93701ZM265.172 7.54901H265.872C268.153 7.54901 270.561 6.77501 270.561 3.93701C270.561 1.55101 268.977 1.16401 266.823 1.16401C266.272 1.17736 265.722 1.22042 265.176 1.29301L265.172 7.54901ZM265.172 12.708C265.172 15.808 265.172 16.513 266.946 16.513C269.607 16.513 271.255 15.413 271.255 12.579C271.255 8.90301 268.655 8.51601 265.616 8.51601H265.172V12.708Z"/>
          <path d="M288.209 17.478L285.358 9.999H279.466C278.326 12.32 277.122 14.963 277.122 16.446C277.112 16.7913 277.134 17.1367 277.187 17.478H273.887L274.457 16.704C275.978 14.77 281.363 3.294 281.363 1.104V0.391998H284.463C286.173 5.743 287.821 11.546 290.482 16.446L290.989 17.413L288.209 17.478ZM283.078 3.229C283.012 3.036 282.888 2.584 282.634 2.584C282.38 2.584 282.254 3.1 282.19 3.229L279.91 8.972H284.915L283.078 3.229Z"/>
          <path d="M309.562 0.456998C308.928 1.489 309.055 2.908 309.055 4.257C308.928 7.481 309.055 10.77 309.245 13.995C309.292 15.1979 309.572 16.3803 310.068 17.477H306.2C306.629 15.9026 306.8 14.2691 306.707 12.64V3.81C306.707 3.552 306.707 3.23 306.517 3.23C306.327 3.23 306.263 3.423 306.2 3.617L300.307 17.805L295.3 4.649C294.983 3.875 294.793 3.23 294.54 3.23C294.287 3.23 294.286 3.746 294.286 4.13V12.836C294.286 14.9 294.286 16.636 294.857 17.544H291.7L291.953 17.222C292.903 15.803 293.03 11.547 293.03 8.709V1.94C293.03 1.231 293.03 0.839998 292.396 0.456998H295.628C295.945 0.456998 296.328 0.520998 296.451 0.843998L300.316 12.516C300.442 12.903 300.506 13.354 300.759 13.354C301.012 13.354 301.076 13.096 301.203 12.709L305.828 1.552C306.077 0.971998 306.267 0.391998 306.9 0.391998L309.562 0.456998Z"/>
          <path d="M325.148 17.478L322.3 9.999H316.4C315.26 12.32 314.119 14.963 314.119 16.446C314.109 16.7913 314.131 17.1368 314.185 17.478H310.885L311.455 16.704C312.976 14.77 318.361 3.294 318.361 1.104V0.391998H321.466C323.177 5.743 324.824 11.546 327.485 16.446L327.992 17.413L325.148 17.478ZM320.017 3.229C319.951 3.036 319.826 2.584 319.573 2.584C319.32 2.584 319.193 3.1 319.129 3.229L316.848 8.972H321.853L320.017 3.229Z"/>
          <path d="M330.063 3.71504C330.251 3.71504 330.404 3.68813 330.524 3.635C330.643 3.58125 330.703 3.45285 330.703 3.2489C330.703 3.15813 330.682 3.08596 330.641 3.03221C330.599 2.97885 330.546 2.93737 330.481 2.90782C330.415 2.87868 330.343 2.85848 330.262 2.84776C330.181 2.8372 330.104 2.83158 330.031 2.83158H329.485V3.71504H330.063ZM330.07 2.30944C330.482 2.30944 330.799 2.38448 331.02 2.53468C331.241 2.68413 331.352 2.94144 331.352 3.30558C331.352 3.46065 331.33 3.59358 331.285 3.7027C331.241 3.81251 331.18 3.90281 331.102 3.97229C331.023 4.04177 330.932 4.09558 330.829 4.13253C330.724 4.16999 330.612 4.19414 330.492 4.2047L331.368 5.67484H330.688L329.891 4.23717H329.485V5.67484H328.836V2.30944H330.07ZM327.969 4.94381C328.084 5.23291 328.24 5.48322 328.438 5.69503C328.636 5.90633 328.869 6.07105 329.137 6.18871C329.405 6.30684 329.693 6.36576 330 6.36576C330.302 6.36576 330.588 6.30684 330.856 6.18871C331.124 6.07105 331.357 5.90633 331.555 5.69503C331.753 5.48322 331.91 5.23291 332.027 4.94381C332.145 4.65472 332.204 4.33872 332.204 3.99627C332.204 3.65342 332.145 3.3392 332.027 3.05234C331.91 2.76595 331.753 2.51833 331.555 2.30944C331.357 2.10032 331.124 1.93745 330.856 1.81978C330.588 1.70211 330.302 1.64273 330 1.64273C329.693 1.64273 329.405 1.70211 329.137 1.81978C328.869 1.93745 328.636 2.10032 328.438 2.30944C328.24 2.51833 328.084 2.76595 327.969 3.05234C327.854 3.3392 327.797 3.65342 327.797 3.99627C327.797 4.33872 327.854 4.65472 327.969 4.94381ZM327.247 2.75923C327.411 2.39011 327.63 2.07525 327.906 1.8153C328.182 1.55576 328.502 1.35519 328.863 1.2129C329.225 1.07126 329.604 1 330 1C330.396 1 330.775 1.07126 331.137 1.2129C331.499 1.35519 331.818 1.55576 332.094 1.8153C332.37 2.07525 332.59 2.39011 332.754 2.75923C332.919 3.12853 333 3.54092 333 3.99627C333 4.45685 332.919 4.87141 332.754 5.24117C332.59 5.61053 332.37 5.92653 332.094 6.18871C331.818 6.45136 331.499 6.65193 331.137 6.79157C330.775 6.93052 330.396 7 330 7C329.604 7 329.225 6.93052 328.863 6.79157C328.502 6.65193 328.182 6.45136 327.906 6.18871C327.63 5.92653 327.411 5.61053 327.247 5.24117C327.083 4.87141 327 4.45685 327 3.99627C327 3.54092 327.083 3.12853 327.247 2.75923Z"/>
        </g>
      </svg>
    </div>
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

# Per-gate accent/cover colours  (cycles via modulo for gates > 7)
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
    "cover_bg":    "#fafaf8",
    "cover_dim":   "#6b6f7b",
    "cover_accent": "#1c1e24",
    "fold_color":  "#b8b5ac",
}

def _theme(order):
    palette = _THEME_PALETTE[(order - 1) % len(_THEME_PALETTE)]
    return {**_THEME_BASE, **palette}

GATE_THEMES = {i + 1: {**_THEME_BASE, **p} for i, p in enumerate(_THEME_PALETTE)}


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
        'a staff member will mark this gate complete once they see you finish.</p>'
    )


def _body_match_pairs(cfg, team, act):
    """Packet for social engineering: technique reference table only."""
    technique_descriptions = cfg.get("technique_descriptions", [])

    if technique_descriptions:
        rows = "".join(
            f'<tr><td>{_h(td["name"])}</td><td>{_h(td["description"])}</td></tr>'
            for td in technique_descriptions
        )
        return (
            '      <p>Use this reference to identify which technique each scenario on the web page is using:</p>\n'
            '      <table class="technique-table">\n'
            '        <thead><tr><th>Technique</th><th>Description</th></tr></thead>\n'
            f'        <tbody>{rows}</tbody>\n'
            '      </table>\n'
        )

    return '      <p>(No technique descriptions defined.)</p>'


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

        # Try to load plain-text passwords and login_url from sessions/<slug>.json
        password_map = {}
        login_url = ""
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
                    login_url = data.get("login_url", "")
                    self.stdout.write(f"  Passwords loaded from {candidate}")
                    if login_url:
                        self.stdout.write(f"  Login URL: {login_url}")
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

                # Login URL block for cover
                if login_url:
                    url_html = (
                        '<div class="cover-url-label">Login at</div>'
                        f'<div class="cover-url">{_h(login_url)}</div>'
                    )
                else:
                    url_html = ""

                html = PAGE_HTML.format(
                    session_name  = _h(session.name),
                    team_name     = _h(team.name),
                    order         = act.order,
                    title         = _h(act.title),
                    password_html = password_html,
                    url_html      = url_html,
                    cs_block_html = cs_block,
                    body_html     = body,
                    **theme,
                )

                safe = team.name.replace(" ", "_")
                out_path = out_dir / f"{safe}-gate-{act.order}.html"
                out_path.write_text(html, encoding="utf-8")
                self.stdout.write(f"  {out_path}")
                count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n{count} sheet(s) written to {out_dir}/ "
            f"({len(teams)} team(s) × {len(activities)} gate(s)).\n"
            "Open any file in a browser and use File → Print."
        ))
