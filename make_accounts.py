#!/usr/bin/env python3
"""
make_accounts.py — accounts.json generator for PrismLauncher
(formatVersion 3).

Creates a file with two accounts:
  * Offline — active by default;
  * MSA     — with the launcher's real client ID (does not fall back
              to Disabled).

A note on MSA:
  the client ID is baked into the launcher build
  (CMakeLists.txt: Launcher_MSA_CLIENT_ID) and is checked on every
  refresh (MSAStep.cpp). If your build overrides it (or if
  MSAClientIDOverride is set in prismlauncher.cfg), pass it in via
  --client-id.

Usage:
    python make_accounts.py <offline_name> [--msa <msa_name>]
            [--client-id <uuid>] [-o <path>] [--active {offline,msa}]

Examples:
    # Windows (cmd.exe; %APPDATA% is expanded by the shell)
    python make_accounts.py Steve
    python make_accounts.py Steve --msa Alex -o "%APPDATA%/PrismLauncher/accounts.json"

    # Windows (PowerShell)
    python make_accounts.py Steve --msa Alex -o "$env:APPDATA/PrismLauncher/accounts.json"

    # Linux — native package, AppImage, or portable build
    python3 make_accounts.py Steve --msa Alex \
        -o ~/.local/share/PrismLauncher/accounts.json

    # Linux — Flatpak
    python3 make_accounts.py Steve --msa Alex \
        -o ~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/accounts.json

    # macOS
    python3 make_accounts.py Steve --msa Alex \
        -o "~/Library/Application Support/PrismLauncher/accounts.json"
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import secrets
import sys
import time
import uuid
from pathlib import Path

FORMAT_VERSION = 3
# Exact client ID from PrismLauncher/CMakeLists.txt (Launcher_MSA_CLIENT_ID)
DEFAULT_CLIENT_ID = "c36a9fb6-4f2a-41ff-90bd-ae7cc92031eb"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")
# Was: TOKEN_TTL = 86400 (24 hours)
TOKEN_TTL = 10 * 365 * 86400  # 10 years

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def fake_jwt(payload: dict, kid: str | None = None) -> str:
    """Plausible JWT: real header/payload, random signature."""
    header = {"alg": "RS256", "typ": "JWT"}
    if kid:
        header["kid"] = kid
    h = b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
    p = b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    s = b64url(secrets.token_bytes(64))
    return f"{h}.{p}.{s}"


def offline_uuid(name: str) -> str:
    """Offline player UUID: MD5("OfflinePlayer:<name>") + v3/variant bits."""
    digest = bytearray(
        hashlib.md5(f"OfflinePlayer:{name}".encode("utf-8")).digest()
    )
    digest[6] = (digest[6] & 0x0F) | 0x30  # version 3
    digest[8] = (digest[8] & 0x3F) | 0x80  # IETF variant
    return uuid.UUID(bytes=bytes(digest)).hex


def build_offline_account(name: str, now: int, active: bool) -> dict:
    account = {
        "type": "Offline",
        "ygg": {
            "iat": now,
            "token": "0",
            "extra": {
                "clientToken": uuid.uuid4().hex,
                "userName": name,
            },
        },
        "profile": {
            "id": offline_uuid(name),
            "name": name,
            "skin": {"id": "", "url": "", "variant": ""},
            "capes": [],
        },
    }
    if active:
        account["active"] = True
    return account


def build_msa_account(name: str, now: int, active: bool,
                      client_id: str) -> dict:
    """MSA account; client_id must match the one baked into the launcher."""
    exp = now + TOKEN_TTL
    xuid = str(2533274862337000 + secrets.randbelow(10**6))
    uhs = str(2533274862337000 + secrets.randbelow(10**6))
    mc_uuid = uuid.uuid4().hex

    account = {
        "type": "MSA",
        # Critical: MSAStep.cpp compares this against
        # BuildConfig.MSA_CLIENT_ID
        "msa-client-id": client_id,
        "msa": {
            "iat": now,
            "exp": exp,
            "token": fake_jwt(
                {
                    "aud": "00000000-0000-0000-0000-00000000772d",
                    "iss": "https://login.microsoftonline.com/consumers/v2.0",
                    "iat": now,
                    "exp": exp,
                    "sub": secrets.token_hex(8).upper(),
                }
            ),
            "refresh_token": "0." + secrets.token_urlsafe(180),
            "extra": {
                "ext_expires_in": TOKEN_TTL,
                "token_type": "Bearer",
            },
        },
        "utoken": {
            "iat": now,
            "exp": exp,
            "token": fake_jwt(
                {
                    "iss": "https://user.auth.xboxlive.com",
                    "iat": now, "exp": exp,
                    "xuid": xuid, "uhs": uhs,
                }
            ),
            "extra": {"uhs": uhs},
        },
        "xrp-mc": {
            "iat": now,
            "exp": exp,
            "token": fake_jwt(
                {
                    "iss": "https://xsts.auth.xboxlive.com",
                    "iat": now, "exp": exp,
                    "relyingParty": "rp://api.minecraftservices.com/",
                    "xuid": xuid, "uhs": uhs,
                }
            ),
            "extra": {"uhs": uhs},
        },
        "ygg": {
            "iat": now,
            "exp": exp,
            "token": fake_jwt(
                {
                    "iss": "https://api.minecraftservices.com/",
                    "iat": now, "exp": exp,
                    "sub": mc_uuid, "spr": mc_uuid,
                    "xuid": xuid, "agg": "Adult",
                    "platform": "PC_LAUNCHER",
                    "roles": [],
                }
            ),
            "extra": {
                "clientToken": uuid.uuid4().hex,
                "userName": name,
            },
        },
        "profile": {
            "id": mc_uuid,
            "name": name,
            "skin": {
                "id": str(uuid.uuid4()),
                "url": "https://textures.minecraft.net/texture/"
                       + secrets.token_hex(32),
                "variant": "classic",
            },
            "capes": [],
        },
        "entitlement": {
            "ownsMinecraft": True,
            "canPlayMinecraft": True,
        },
    }
    if active:
        account["active"] = True
    return account


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="accounts.json generator (PrismLauncher, formatVersion 3)"
    )
    parser.add_argument("name", help="offline account username")
    parser.add_argument("--msa", help="MSA account username (defaults to offline)")
    parser.add_argument(
        "--client-id", default=DEFAULT_CLIENT_ID,
        help="MSA client ID of your launcher build "
             f"(default {DEFAULT_CLIENT_ID})",
    )
    parser.add_argument("-o", "--output", default="accounts.json",
                        help='where to save ("-" means stdout); "~" is expanded')
    parser.add_argument("--active", choices=["offline", "msa"],
                        default="offline",
                        help="active account (offline by default)")
    args = parser.parse_args(argv[1:])

    offline_name = args.name
    msa_name = args.msa or offline_name
    for nick in (offline_name, msa_name):
        if not USERNAME_RE.fullmatch(nick):
            print(f"Error: invalid username {nick!r}", file=sys.stderr)
            return 2

    now = int(time.time())
    offline = build_offline_account(
        offline_name, now, active=args.active == "offline"
    )
    msa = build_msa_account(
        msa_name, now, active=args.active == "msa",
        client_id=args.client_id,
    )

    data = {"accounts": [msa, offline], "formatVersion": FORMAT_VERSION}
    text = json.dumps(data, ensure_ascii=False, indent=4, sort_keys=True)

    if args.output == "-":
        print(text)
    else:
        out_path = Path(args.output).expanduser()
        try:
            if out_path.exists():
                out_path.with_name(out_path.name + ".bak").write_bytes(
                    out_path.read_bytes()
                )
            out_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"Write error: {exc}", file=sys.stderr)
            return 1
        print(f"Written: {out_path.resolve()}", file=sys.stderr)

    print(f"  MSA:     {msa_name} (client-id: {args.client_id})",
          file=sys.stderr)
    print(f"  Offline: {offline_name} (uuid: {offline['profile']['id']})",
          file=sys.stderr)
    print(f"  Active:  {args.active}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
