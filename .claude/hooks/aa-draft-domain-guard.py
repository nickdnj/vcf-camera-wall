#!/usr/bin/env python3
"""PreToolUse guard: keep bare domain names out of Gmail connector drafts.

The claude.ai Gmail connector (create_draft / update_draft) rewrites any text
that looks like a domain -- "infoage.org", "new.infoage.org" -- into
  https://www.google.com/url?q=http://<domain>&source=gmail&ust=<ts>&sa=E)
in BOTH the plain-text and HTML parts of the stored message. The recipient gets
a mangled sentence, not just a tracked link. Found 2026-11-15 by reading a
draft back with get_draft messageFormat RAW.

This hook blocks the call before the damage, while the body is still clean.
It flags bare domains only: email addresses (you@example.com) and full URLs with a
scheme (https://x.org) are let through. Whether the connector rewrites those
too is not verified, so the operating notes also tell agents to read every
draft back and check for "google.com/url?q=".

Covers the claude.ai connector (create_draft / update_draft) and the local gmail /
gmail-personal MCP servers (draft_email: subject, body, htmlBody). Every string field
in tool_input is scanned except recipient/id fields, so body and htmlBody are covered.

Factory-managed: edit templates/portable/hooks/ in AgentArchitect, then `aa sync`.
"""
import json
import re
import sys

# Fields that name people, not body text.
SKIP_KEYS = {"to", "cc", "bcc", "recipients", "from", "threadid", "draftid",
             "messageid", "id"}
# Common TLDs only, so file names (SKILL.md, app.py) and "e.g." don't match.
TLDS = ("com|org|net|edu|gov|mil|io|ai|app|dev|co|us|uk|ca|info|biz|me|tv|"
        "ly|xyz|site|online|tech|cloud|page|museum|local")
# Not preceded by @ (email), / or : (inside a URL), or another domain char.
BARE_DOMAIN_RE = re.compile(
    r"(?<![@/:\w.-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:" + TLDS + r"))(?![\w-]|\.[a-z0-9])",
    re.IGNORECASE)


def norm(key):
    return key.lower().replace("_", "")


def texts(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if norm(k) not in SKIP_KEYS:
                texts(v, out)
    elif isinstance(node, list):
        for v in node:
            texts(v, out)
    elif isinstance(node, str):
        out.append(node)


try:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {}) or {}
except Exception:
    sys.exit(0)  # not a safety gate; never block on a parse failure

strings = []
texts(tool_input, strings)
found = sorted({m.group(1) for s in strings for m in BARE_DOMAIN_RE.finditer(s)})
if found:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            "Draft domain guard: the Gmail connector rewrites bare domain names into "
            "google.com/url?q=... redirects inside the message text, which mangles the "
            f"sentence for the recipient. Found: {', '.join(found)}. Reword without the "
            "domain (\"the InfoAge site\"), or give the full link with https:// and read "
            "the draft back (get_draft on the connector; read_email on the local servers) to confirm it contains no \"google.com/url?q=\".")}}))
sys.exit(0)
