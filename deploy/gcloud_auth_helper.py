#!/usr/bin/env python3
"""Keep gcloud auth login alive, print OAuth URL, wait for code file."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

GCLOUD = Path(os.environ.get("LOCALAPPDATA", "")) / "google-cloud-sdk" / "bin" / "gcloud.cmd"
URL_FILE = Path(os.environ.get("TEMP", ".")) / "gcloud-auth-url.txt"
CODE_FILE = Path(os.environ.get("TEMP", ".")) / "gcloud-auth-code.txt"
STATUS_FILE = Path(os.environ.get("TEMP", ".")) / "gcloud-auth-status.txt"
PY312 = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "python.exe"


def main() -> int:
    if not GCLOUD.is_file():
        print("gcloud not found", file=sys.stderr)
        return 1

    env = os.environ.copy()
    if PY312.is_file():
        env["CLOUDSDK_PYTHON"] = str(PY312)

    for p in (URL_FILE, CODE_FILE, STATUS_FILE):
        if p.exists():
            p.unlink()

    STATUS_FILE.write_text("starting\n", encoding="utf-8")
    proc = subprocess.Popen(
        [str(GCLOUD), "auth", "login", "--no-launch-browser"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    assert proc.stdout is not None
    assert proc.stdin is not None

    buf = ""
    url = None
    deadline = time.time() + 45
    while time.time() < deadline and url is None:
        chunk = proc.stdout.read(1)
        if not chunk:
            if proc.poll() is not None:
                break
            time.sleep(0.05)
            continue
        buf += chunk
        # gcloud wraps the URL across lines; flatten whitespace after the scheme.
        flat = re.sub(r"\s+", "", buf)
        m = re.search(
            r"https://accounts\.google\.com/o/oauth2/auth\?[A-Za-z0-9\-._~%&=+]+",
            flat,
        )
        if m and m.group(0).endswith("code_challenge_method=S256"):
            url = m.group(0)
            break
        if "enter the verification code" in buf.lower():
            m2 = re.search(
                r"(https://accounts\.google\.com/o/oauth2/auth\?.*?code_challenge_method=S256)",
                flat,
            )
            if m2:
                url = m2.group(1)
                break

    if not url:
        STATUS_FILE.write_text(f"no-url\n{buf}\n", encoding="utf-8")
        proc.kill()
        print(buf)
        return 1

    URL_FILE.write_text(url + "\n", encoding="utf-8")
    STATUS_FILE.write_text("waiting-code\n", encoding="utf-8")
    print(url, flush=True)

    code_deadline = time.time() + 300
    code = None
    while time.time() < code_deadline:
        if CODE_FILE.is_file():
            raw = CODE_FILE.read_text(encoding="utf-8").strip()
            if raw:
                code = raw.splitlines()[0].strip()
                break
        if proc.poll() is not None:
            STATUS_FILE.write_text(f"exited-early\n{proc.returncode}\n", encoding="utf-8")
            return proc.returncode or 1
        time.sleep(0.5)

    if not code:
        STATUS_FILE.write_text("timeout-code\n", encoding="utf-8")
        proc.kill()
        return 1

    proc.stdin.write(code + "\n")
    proc.stdin.flush()
    out, _ = proc.communicate(timeout=60)
    STATUS_FILE.write_text(f"done\n{proc.returncode}\n{out}\n", encoding="utf-8")
    print(out)
    return proc.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())
