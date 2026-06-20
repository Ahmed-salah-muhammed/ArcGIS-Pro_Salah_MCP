"""Diagnose a GitHub token for the 'Deploy Web App' pipeline.

Run it in YOUR OWN terminal so the token never leaves your machine. It reads the
token from the GH_TOKEN env var, or prompts (hidden input) if that's unset:

    python demos/check_github_token.py
    python demos/check_github_token.py --try-create   # actually create+delete a test repo

It reports the token TYPE (classic vs fine-grained), classic scopes, and — with
--try-create — whether it can really create a repository (the exact call the
deploy uses: POST /user/repos).
"""
from __future__ import annotations

import os
import sys
import uuid
from getpass import getpass

import urllib.request
import urllib.error
import json

API = "https://api.github.com"
HDRS_VER = "2022-11-28"


def _req(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", HDRS_VER)
    req.add_header("User-Agent", "salah-mcp-token-check")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


def main() -> None:
    token = os.environ.get("GH_TOKEN") or getpass("Paste GitHub token (hidden): ").strip()
    if not token:
        print("No token provided.")
        return

    kind = ("fine-grained" if token.startswith("github_pat_")
            else "classic" if token.startswith("ghp_")
            else "unknown/other")
    print(f"\nToken prefix → type: {kind}")

    status, headers, text = _req("GET", "/user", token)
    if status != 200:
        print(f"GET /user FAILED (HTTP {status}): {text[:200]}")
        print("The token is invalid or expired. Generate a new one.")
        return
    login = json.loads(text).get("login")
    scopes = headers.get("X-OAuth-Scopes", "")
    print(f"Authenticated as: {login}")

    if kind == "classic" or scopes:
        print(f"Classic token scopes: [{scopes or '(none)'}]")
        if "repo" in [s.strip() for s in scopes.split(",")]:
            print("✓ Has 'repo' scope — should be able to create repositories.")
        else:
            print("✗ Missing the 'repo' scope — add it (regenerate the classic token).")
    else:
        print("Fine-grained token: the API can't list its permissions here.")
        print("Verify on github.com → token settings:")
        print("  • Repository access = 'All repositories'  (NOT 'Only select repositories')")
        print("  • Permissions: Administration + Contents + Pages = Read and write")

    if "--try-create" in sys.argv:
        name = "salah-mcp-token-test-" + uuid.uuid4().hex[:8]
        print(f"\n--try-create: POST /user/repos  (name={name}) ...")
        st, _, tx = _req("POST", "/user/repos", token,
                         {"name": name, "private": True, "auto_init": True})
        if st == 201:
            print("✓ CREATE OK — this token CAN create repositories.")
            # Now test writing a file (the contents API the deploy uses to push).
            import base64
            cpath = f"/repos/{login}/{name}/contents/hello.txt"
            cst, _, ctx = _req("PUT", cpath, token, {
                "message": "token test", "branch": "main",
                "content": base64.b64encode(b"hello from salah mcp").decode(),
            })
            if cst in (200, 201):
                print("✓ PUSH OK — this token CAN write files. The deploy will work fully.")
            else:
                print(f"✗ PUSH FAILED (HTTP {cst}): {ctx[:200]}")
                print("  → add 'Contents: Read and write' to the token (or use classic 'repo').")
            dst, _, dtx = _req("DELETE", f"/repos/{login}/{name}", token)
            if dst == 204:
                print("  (cleaned up the test repo)")
            else:
                print(f"  NOTE: couldn't delete test repo (HTTP {dst}). Delete '{name}' "
                      "manually on GitHub; deletion needs the 'delete_repo' scope.")
        else:
            print(f"✗ CREATE FAILED (HTTP {st}): {tx[:200]}")
            print("  → fix the token per the notes above, then re-run.")


if __name__ == "__main__":
    main()
