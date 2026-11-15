"""Scan tracked working-tree files; print locations only, never matched credentials.
Heuristic defense only: provider scanning and credential rotation remain necessary.
"""
import re
import subprocess
import sys
from pathlib import Path

patterns = {
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "GitHub token": r"gh[pousr]_[A-Za-z0-9]{30,}",
    "OpenAI key": r"sk-(?:proj-)?[A-Za-z0-9_-]{40,}",
    "Google API key": r"AIza[A-Za-z0-9_-]{30,}",
    "AWS access key": r"AKIA[0-9A-Z]{16}",
    "Telegram token": r"\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}",
    "Supabase server key": r"sb_secret_[A-Za-z0-9_-]{20,}",
}
failed = False
for raw in subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0"):
    if not raw:
        continue
    path = Path(raw.decode())
    if not path.is_file():
        continue
    text = path.read_bytes().decode("utf-8", errors="ignore")
    for kind, pattern in patterns.items():
        for match in re.finditer(pattern, text):
            line = text.count("\n", 0, match.start()) + 1
            print(f"{path}:{line}: possible {kind} (value redacted)")
            failed = True
sys.exit(1 if failed else 0)
