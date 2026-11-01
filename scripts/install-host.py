"""Validate/install Saha host wiring; installation never starts/restarts services."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def render(stage):
    files = {}
    for source in (ROOT / "deploy/host/systemd").glob("*.service"):
        text = source.read_text().replace("@REPO@", str(ROOT)).replace("@USER@", ROOT.owner())
        files[Path("/etc/systemd/system") / source.name] = text
    for name, folder in [("00-saha-proxy.conf", "conf.d"), ("saha-proxy-headers.conf", "snippets"),
                         ("saha-marketplace", "sites-available"), ("saha-admin", "sites-available")]:
        files[Path("/etc/nginx") / folder / name] = (ROOT / "deploy/host/nginx" / name).read_text()
    files[Path("/usr/local/bin/saha")] = "#!/bin/sh\nexec " + shlex.quote(str(ROOT / "bin/saha")) + ' "$@"\n'
    for destination, text in files.items():
        file = stage / destination.relative_to("/")
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
    return files


def validate(stage):
    units = list((stage / "etc/systemd/system").glob("*.service"))
    result = subprocess.run(["systemd-analyze", "verify", "--man=no", *map(str, units)], capture_output=True, text=True)
    if result.returncode:
        print(result.stderr, end="")
        raise RuntimeError("systemd unit verification failed")
    print("Saha systemd unit verification passed", flush=True)
    nginx = stage / "etc/nginx"
    for name in ("saha-marketplace", "saha-admin"):
        file = nginx / "sites-available" / name
        file.write_text(file.read_text().replace("/etc/nginx/snippets/", str(nginx / "snippets") + "/")
                        .replace("access_log /var/log/nginx/saha-access.log saha_access;", "access_log off;")
                        .replace("access_log /var/log/nginx/saha-admin-access.log saha_access;", "access_log off;"))
    config = stage / "nginx-test.conf"
    config.write_text(f"error_log stderr;\npid {stage}/nginx.pid;\nevents {{}}\nhttp {{\ninclude {nginx}/conf.d/00-saha-proxy.conf;\ninclude {nginx}/sites-available/saha-marketplace;\ninclude {nginx}/sites-available/saha-admin;\n}}\n")
    subprocess.run(["nginx", "-t", "-p", str(stage), "-c", str(config)], check=True)
    subprocess.run(["cloudflared", "tunnel", "--config", "/etc/cloudflared/config.yml", "ingress", "validate"], check=True)


def install(files):
    if os.geteuid() != 0:
        raise SystemExit("Installation writes /etc and /usr/local; run this command with sudo from a normal host terminal.")
    backup = Path(tempfile.mkdtemp(prefix="saha-host-backup-", dir="/var/backups"))
    previous = {}
    links = {Path("/etc/nginx/sites-enabled") / name: Path("/etc/nginx/sites-available") / name
             for name in ("saha-marketplace", "saha-admin")}
    destinations = list(files) + list(links)
    try:
        for destination in destinations:
            existed = destination.exists() or destination.is_symlink()
            if existed:
                saved = backup / destination.relative_to("/")
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, saved, follow_symlinks=False)
            previous[destination] = existed
        for destination, text in files.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Replace the directory entry rather than follow an old symlink.
            if destination.is_symlink():
                destination.unlink()
            destination.write_text(text)
            destination.chmod(0o755 if destination == Path("/usr/local/bin/saha") else 0o644)
        for destination, target in links.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                destination.unlink()
            destination.symlink_to(target)
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
    except BaseException:
        for destination, existed in previous.items():
            if destination.exists() or destination.is_symlink():
                destination.unlink()
            if existed:
                shutil.copy2(backup / destination.relative_to("/"), destination, follow_symlinks=False)
        print(f"Installation failed; original files restored. Backup: {backup}")
        raise
    print(f"Installed host wiring. Original files: {backup}")
    print("No services were started/restarted and nginx was not reloaded. Complete release migrations/builds before activation; see docs/HOSTING.md.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and os.geteuid() != 0:
        parser.error("--apply requires sudo on the host")
    stage = Path(tempfile.mkdtemp(prefix="saha-host-check-"))
    files = render(stage)
    print(f"Reviewable staged files: {stage}", flush=True)
    validate(stage)
    if args.apply:
        install(files)
    else:
        print("Host wiring syntax verified. No system files or running services changed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Host wiring validation/installation failed ({type(exc).__name__}). No services were activated; inspect the preceding check output.")
