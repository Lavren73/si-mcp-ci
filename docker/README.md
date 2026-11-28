# Hermes agent image for SI-MCP tests (`hermes-si`)

Recipe: [`hermes-si.Dockerfile`](./hermes-si.Dockerfile). Built on `nousresearch/hermes-agent:latest`.

Self-hosted GitHub Actions runner image (`si1c-runner` / container `si1c-ci`):
recipe and capture/recreate procedure in [`si1c-runner/`](./si1c-runner/) (задача SI-MCP #640 §5).

## What is baked into the image (public, no secrets)
- Temurin **JDK 17** (`/opt/jdk-17`, as CI) + **Maven** — `mvn compile` / `mvn verify`.
- **gh** CLI, **pnpm** (symlinked into `/usr/local/bin`).
- **xvfb** + GTK3 / WebKit / SWT runtime libraries (Debian 13 `t64`) — needed to run
  `xvfb-run mvn verify` (Tycho surefire requires a display) and the 1C:EDT IDE.
- `PATH` prepends `/opt/tools/bin` (launchers for the mounted test stack).

## What is NOT in the image (private, host-side bind mounts)
The 1C platform, EDT, test frameworks and the 1C license are large and/or licensed, so they
live on the host and are mounted at run time — never committed to this public repo:

| Host dir | Container mount | Contents |
|---|---|---|
| `~/hermes-tools` | `/opt/tools` | `1cv8/` (1C:Enterprise 8.3.27.2342), `si-edt/` (EDT 2026.2.2 + bundled Axiom JDK 25), `frameworks/` (YAxUnit `.cfe`, Vanessa Automation), `bin/` (launchers) |
| `~/hermes-data` | `/opt/data` | Hermes profile, incl. `.1cv8/1C/1cv8/conf/*.lic` (1C software license) |

### Provisioning the test stack (one-time, from the CI runner)
On the host that also runs the `si1c-ci` runner container:
```bash
mkdir -p ~/hermes-tools/frameworks
docker cp si1c-ci:/opt/1cv8   ~/hermes-tools/1cv8
docker cp si1c-ci:/opt/si-edt ~/hermes-tools/si-edt
# YAxUnit extension shipped by the self-hosted test workflow:
docker cp si1c-ci:/home/runner/.../YAxUnit-25.12.cfe ~/hermes-tools/frameworks/
```
Vanessa Automation (not present in the runner) is downloaded from the public releases of
`Pr-Mex/vanessa-automation` (e.g. tag `1.2.043.47`: `vanessa-automation*.zip`, `VAExtension*.cfe`)
into `~/hermes-tools/frameworks/vanessa/`.

### Launchers (`~/hermes-tools/bin`, editable without rebuilding)
- `1cv8`, `1cv8c`, `1cv8s` → `/opt/tools/1cv8/x86_64/<version>/…`
- `1cedt`, `1cedtcli` → `/opt/tools/si-edt/components/1c-edt-2026.*/…` with `JAVA_HOME` set to
  the bundled Axiom JDK 25 (EDT 2026.2 requires Java 25; Maven/Tycho still use Temurin 17).

## 1C license
The runner uses a **software license** stored in its profile
(`~/.1cv8/1C/1cv8/conf/<timestamp>.lic`); there is no license server (`conf.cfg` only sets
`SystemLanguage=System`). Copy that `.lic` into the agent profile:
```bash
docker exec -u root hermes mkdir -p /opt/data/.1cv8/1C/1cv8/conf
docker cp si1c-ci:/home/runner/.1cv8/1C/1cv8/conf/<timestamp>.lic /tmp/1c.lic
docker cp /tmp/1c.lic hermes:/opt/data/.1cv8/1C/1cv8/conf/
docker exec -u root hermes chown -R hermes:hermes /opt/data/.1cv8
```
A 1C software license is bound to computer parameters. Containers on the **same physical host**
share the hardware, so the copied license is often accepted; if 1C reports a license error,
re-activate it (enter the pin code via the 1C licensing dialog / `1cv8` license acquisition, or
web activation at `https://portal.1c.ru`). The license file itself is private — keep it out of git.
**Confirmed 2026-11-22 20:53–20:55 UTC (agent №2, LIC techlog):** the copied license IS accepted
in the `hermes` container on the same host — `getLicense res=seize` in 0.35 s (developer license,
«Available in current computer configuration»); the hardware-bound hypothesis was disproven by
measurement. Note: the `.lic` may be **renamed to a new `<timestamp>.lic`** during acquisition
(observed 20:48:34 UTC: `20261110195555.lic` → `20261122204834.lic`, same 5166 bytes; whether the
platform or the session renamed it is unverified) — reference the conf dir, not a fixed filename.

## Run
```bash
docker build -t hermes-si:latest -f docker/hermes-si.Dockerfile .
docker run -d --name hermes --restart unless-stopped \
  -v ~/hermes-data:/opt/data \
  -v ~/hermes-tools:/opt/tools \
  -p 9119:9119 --env-file ~/hermes-dashboard.env \
  hermes-si:latest gateway run
```

## Running the tests
```bash
# headless OSGi / server tests (needs a display):
xvfb-run --auto-servernum mvn -B -ntp -Dstyle.color=never verify
# 1C / YAxUnit / Vanessa run inside 1C:Enterprise via the mounted platform + license.
```
**The license must be under the HOME of the process that runs 1cv8.** 1cv8 reads
`$HOME/.1cv8/1C/1cv8/conf/`, and the agent's HOME is `/opt/data/home`, not `/opt/data`.
Observed 2026-11-22 (agent №2, Linux container): with the `.lic` only in `/opt/data/.1cv8/…`,
`1cv8c CREATEINFOBASE` hung in `poll()` (socket-fd, 9 threads) with zero error output; the
working `si1c-ci` runner on the same host keeps the identical `.lic` at
`/home/runner/.1cv8/…` (= its HOME). Make the conf dir visible in the agent HOME:
```bash
docker exec -u hermes hermes mkdir -p /opt/data/home/.1cv8/1C/1cv8
docker exec -u hermes hermes ln -s /opt/data/.1cv8/1C/1cv8/conf /opt/data/home/.1cv8/1C/1cv8/conf
```
Fix **CONFIRMED** 2026-11-22 20:53–20:55 UTC by agent №2 via LIC techlog (`getLicense res=seize`
in 0.35 s from the symlinked path). The remaining `CREATEINFOBASE` hang is a GUI modal dialog,
not the license — see pitfalls below.

## Known pitfalls
- **EDT needs the bundled Axiom JDK 25, never the system JDK 17.** Launching `1cedt` with
  `JAVA_HOME=/opt/jdk-17` hangs the native launcher: it never spawns a JVM
  (`eclipse_native_launcher.log`: `findJavaComponentFuncPtr returned empty string`).
  Set `JAVA_HOME`/`PATH` to `/opt/tools/si-edt/components/axiom-jdk-full-25.0.4+5-x86_64`
  (the `1cedt` launcher in `/opt/tools/bin` already does this). Verified 2026-11-22
  20:34–20:39 UTC by agent №2: SIGTERM stop → restart with the bundled JDK →
  «SI-EDT endpoint came up automatically on port 12260», `/health` → `phase:ready`,
  disk `mcpAuthToken` adopted as-is (`adoptStoredToken`), bearer 200 / no-token 401.
- **`1cv8c` needs an X display even in console mode.** Without `DISPLAY` it exits instantly
  rc=255: «*** Unable to initialize GTK+ or connect to the windowing system. Is DISPLAY set
  properly?» Run it under `Xvfb :99` with `XAUTHORITY` set (and `LD_LIBRARY_PATH` pointing at
  the 1C libs). Measured 2026-11-22 20:47–20:56 UTC by agent №2.
- **`CREATEINFOBASE` can block on modal GUI dialogs (observed, open).** With the license fixed
  and a display present, `1cv8c CREATEINFOBASE File=…` still hung (killed by timeout, `/Out`
  0 bytes, no infobase dir). A screenshot of `:99` during the hang shows the modal
  «1C:Enterprise startup» infobase-list window plus a «1C:Workmate is not activated» info popup;
  the process sits in `do_poll` on X11 sockets with no techlog events after LIC — it waits for
  user input. `/DisableStartupMessages` does NOT suppress these dialogs. Workaround under
  investigation by agent №2's tuning session: close the dialogs via X automation (e.g.
  `xdotool`, «Don't show again» on the Workmate popup) during the attempt, or find a headless
  key. Do not multiply parallel attempts on the same infobase path.
