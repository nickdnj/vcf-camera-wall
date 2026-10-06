#!/usr/bin/env python3
"""PreToolUse guard: block any email send/reply/forward unless every
recipient is one of Nick's own addresses. Drafts are not matched.

Repo-level copy of ~/.claude/hooks/email-send-guard.py, so cloud and iOS
sessions (which never see user-level settings on the Mac) enforce
"draft, never send" too. On the Mac both copies run and agree.

Factory-managed: edit templates/portable/hooks/ in AgentArchitect, then `aa sync`.

The allowlist is stored as SHA-256 hashes, not addresses, so this file can be
committed in a public repo without publishing anyone's email. To add an
address:  python3 -c "import hashlib; print(hashlib.sha256(b'you@example.com').hexdigest())"
"""
import hashlib
import json
import re
import sys

# SHA-256 of each of Nick's own addresses, lowercased.
ALLOWED_SHA256 = {
    "f9439f8b60df1d99c8d2ba8ea9aef367fb57db973bdbe767d6e5428a6b5187be",
    "0fe84d6628003e7ae8b62ca7e7ffb36f32727cc8cb2690e546bc4a17ec508f00",
}
RECIPIENT_KEYS = {"to", "cc", "bcc", "recipients", "recipient", "to_recipients",
                  "cc_recipients", "bcc_recipients"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def collect(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k.lower() in RECIPIENT_KEYS:
                out.extend(m.lower() for m in EMAIL_RE.findall(json.dumps(v)))
            else:
                collect(v, out)
    elif isinstance(node, list):
        for v in node:
            collect(v, out)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    sys.exit(0)


try:
    data = json.load(sys.stdin)
except Exception:
    deny("Email send guard: could not parse tool input; blocking to be safe.")

recipients = []
collect(data.get("tool_input", {}), recipients)
if not recipients:
    deny("Email send guard: no explicit recipients to verify (replies/forwards "
         "to a thread are blocked). Create a draft instead; Nick sends it himself.")
bad = sorted(set(r for r in recipients
                 if hashlib.sha256(r.encode()).hexdigest() not in ALLOWED_SHA256))
if bad:
    deny("Email send guard: sending is only allowed to Nick's own addresses. "
         f"Blocked recipients: {', '.join(bad)}. Create a draft instead.")
sys.exit(0)
