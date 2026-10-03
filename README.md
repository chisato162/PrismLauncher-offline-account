# PrismLauncher-offline-account
A generator of `accounts.json` for PrismLauncher
A generator of `accounts.json` for [PrismLauncher](https://prismlauncher.org/)
(`formatVersion 3`) that creates a file containing two accounts at once:

- `Offline` — an offline account, active by default;
- `MSA` — an MSA-type account with the launcher's correct client ID (does not
  fall into the `Disabled` state).

### What the script does

- The offline player's UUID is computed as `MD5("OfflinePlayer:<nickname>")`
  with the version 3 and IETF variant bits set — the same thing vanilla does in
  offline mode. Such a UUID will match the one the server assigns in
  `online-mode=false`.
- Plausible but synthetic JWTs are generated for the MSA account: a genuine
  header/payload structure, random signature.
- Before overwriting, the existing file is copied to `*.bak`.

### Quick start

1. Save the script, for example, as `make_accounts.py`.

2. Close PrismLauncher,

3. Add to hosts

    ```
    # linux (`/etc/hosts`)
    127.0.1.1 login.microsoftonline.com

    # windows (`%SystemRoot%\System32\drivers\etc\hosts`)
    127.0.1.1 login.microsoftonline.com
    ```

4. Run the generation.

   ```bash

    # Linux — native package, AppImage, or portable build
    python3 make_accounts.py Steve --msa Alex -o ~/.local/share/PrismLauncher/accounts.json

    # Linux — Flatpak
    python3 make_accounts.py Steve --msa Alex -o ~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/accounts.json

    # NOT TESTED

    # Windows (cmd.exe; %APPDATA% is expanded by the shell)
    python make_accounts.py Steve
    python make_accounts.py Steve --msa Alex -o "%APPDATA%/PrismLauncher/accounts.json"

    # Windows (PowerShell)
    python make_accounts.py Steve --msa Alex -o "$env:APPDATA/PrismLauncher/accounts.json"

    # macOS
    python3 make_accounts.py Steve --msa Alex -o "~/Library/Application Support/PrismLauncher/accounts.json"
   ```

### Command-line parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `name` | required | Offline account nickname (1–16 characters, `A-Z a-z 0-9 _`) |
| `--msa <nickname>` | equal to the offline nickname | MSA account nickname |
| `--client-id <uuid>` | `c36a9fb6-4f2a-41ff-90bd-ae7cc92031eb` | MSA client ID of your launcher build |
| `-o, --output <path>` | `accounts.json` | Where to save; `-` means output to stdout; `~` is expanded |
| `--active {offline,msa}` | `offline` | Which account to mark as active |

Return codes: `0` — success, `1` — file write error, `2` — invalid nickname.

### About the MSA client ID

The client ID is hard-coded into the launcher build (`CMakeLists.txt`,
`Launcher_MSA_CLIENT_ID`) and is checked on every token refresh
(`MSAStep.cpp`). If your `msa-client-id` in `accounts.json` does not match
what the binary expects, the account is displayed as `Disabled`.

The default value in the script is PrismLauncher's official client ID.
If you built the launcher yourself or set `MSAClientIDOverride` in
`prismlauncher.cfg`, pass your own value:

```bash
python3 make_accounts.py Steve --msa Alex --client-id your-uuid -o accounts.json
```

### Limitations and warnings

- The MSA tokens the script generates are synthetic. They were not issued by
  Microsoft and are not validated by Mojang's servers. Such an account does
  not grant real ownership of Minecraft and will not let you join a server in
  `online-mode=true` — the server will verify the session and reject it. The
  MSA account here is needed only for local launches and offline scenarios.
- Using forged tokens and logging into other people's servers may violate the
  Microsoft/Mojang EULA and the rules of a particular server. Use the script
  only where you have the right to do so: your own servers, test environments,
  offline play.
- The script overwrites the target file. The old version is saved alongside as
  `accounts.json.bak`, but no other backups are made.
- `~` in the `-o` parameter is expanded via `Path.expanduser()`. Windows shells
  expand `%APPDATA%` and `$env:APPDATA` on their own, before Python is launched.
- The nickname is validated by the regexp `^[A-Za-z0-9_]{1,16}$`. An invalid
  nickname results in exit code `2` and a message on stderr.

## License

MIT. See [LICENSE](LICENSE).
