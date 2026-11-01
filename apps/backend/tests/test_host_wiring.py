"""Hosting regressions: fail closed before exposure and retain trusted peer IPs."""
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.clientip import client_ip

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def cli():
    loader = importlib.machinery.SourceFileLoader("saha_cli_test", str(ROOT / "bin/saha"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_online_never_starts_tunnel_when_nginx_is_unready(cli, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "require_mapping", lambda: None)
    monkeypatch.setattr(cli, "ready", lambda: False)
    monkeypatch.setattr(cli, "systemctl", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="refusing to expose"):
        cli.online()
    assert calls == []


def test_online_never_starts_tunnel_for_mismatched_running_build(cli, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "require_mapping", lambda: None)
    monkeypatch.setattr(cli, "ready", lambda: True)
    monkeypatch.setattr(cli, "versions", lambda **kwargs: 1)
    monkeypatch.setattr(cli, "systemctl", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="do not match current source"):
        cli.online()
    assert calls == []


def test_source_identity_excludes_secrets_and_build_output_but_tracks_code(tmp_path):
    from app.core.release import source_fingerprint
    (tmp_path / "page.tsx").write_text("first")
    initial = source_fingerprint(tmp_path)
    (tmp_path / ".env.local").write_text("PRIVATE_SECRET=one")
    (tmp_path / ".next").mkdir()
    (tmp_path / ".next/BUILD_ID").write_text("random")
    assert source_fingerprint(tmp_path) == initial
    (tmp_path / "page.tsx").write_text("second")
    assert source_fingerprint(tmp_path) != initial


def test_old_route_manifest_is_rejected_even_without_localhost_url(cli, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    for app in ("frontend", "admin"):
        output = tmp_path / "apps" / app / ".next"
        (output / "static").mkdir(parents=True)
        (output / "server").mkdir()
        (output / "BUILD_ID").write_text("old")
        (output / "static/app.js").write_text("old production code")
        (output / "server/app-paths-manifest.json").write_text('{"/page":"index.js"}')
    problems = cli.build_problems()
    assert any("missing current route /explore/page" in problem for problem in problems)
    assert any("admin build is missing current route" in problem for problem in problems)


async def test_backend_identifies_loaded_build_in_response(client):
    from app.main import BACKEND_BUILD
    result = await client.get("/health/live")
    assert result.status_code == 200
    assert result.headers["X-Saha-Build"] == BACKEND_BUILD
    assert BACKEND_BUILD.startswith("backend-")


def test_online_waits_for_tunnel_public_readiness(cli, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "require_mapping", lambda: None)
    monkeypatch.setattr(cli, "versions", lambda **kwargs: 0)
    statuses = iter([{"status": 502, "ready": False}, {"status": 200, "ready": True}])
    monkeypatch.setattr(cli, "ready", lambda: True)
    monkeypatch.setattr(cli, "systemctl", lambda *args: calls.append(args))
    monkeypatch.setattr(cli, "http_probe", lambda url: next(statuses))
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)
    cli.online()
    assert calls == [("start", "cloudflared")]


@pytest.mark.parametrize("code,body,headers,expected_ready,reason", [
    (200, {"status": "ready", "postgres": "healthy", "redis": "healthy"}, {}, True, None),
    (200, "<html>Sign in</html>", {}, False, "without Saha readiness JSON"),
    (403, "<html>challenge</html>", {"CF-Mitigated": "challenge", "CF-Ray": "test-ray"}, False, "Cloudflare challenge"),
    (403, {"detail": "Forbidden"}, {"Server": "cloudflare"}, False, "not yet established"),
])
def test_health_probe_distinguishes_ready_json_from_gateway_pages(cli, monkeypatch, code, body, headers, expected_ready, reason):
    class Response(io.BytesIO):
        status = code
        def geturl(self): return "https://sahasolutions.com/health/ready"
    payload = json.dumps(body).encode() if isinstance(body, dict) else body.encode()
    response = Response(payload)
    response.headers = headers
    monkeypatch.setattr(cli.urllib.request, "build_opener", lambda *args: SimpleNamespace(open=lambda *args, **kwargs: response))
    result = cli.http_probe("https://sahasolutions.com/health/ready")
    assert result["ready"] is expected_ready
    assert result["status"] == code
    if reason:
        assert reason in result["reason"]
    assert "body" not in result


def test_uninstalled_group_never_stops_existing_tunnel(cli, monkeypatch):
    calls = []
    def missing_mapping():
        raise RuntimeError("Grouped service is not installed")
    monkeypatch.setattr(cli, "require_mapping", missing_mapping)
    monkeypatch.setattr(cli, "systemctl", lambda *args: calls.append(args))
    monkeypatch.setattr(sys, "argv", ["saha", "start"])
    with pytest.raises(RuntimeError, match="not installed"):
        cli.main()
    assert calls == []


def test_local_start_unpublishes_then_checks_apps_without_reopening_tunnel(cli, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "require_mapping", lambda: None)
    monkeypatch.setattr(cli, "versions", lambda **kwargs: 0)
    monkeypatch.setattr(cli, "systemctl", lambda *args: calls.append(args))
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "wait_ready", lambda: calls.append(("ready",)))
    monkeypatch.setattr(cli, "online", lambda: calls.append(("online",)))
    monkeypatch.setattr(sys, "argv", ["saha", "start", "--local"])
    assert cli.main() == 0
    assert calls == [("stop", "cloudflared"), ("start", "saha"), ("reload", "nginx"), ("ready",)]


def test_failed_app_start_does_not_reopen_tunnel(cli, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "require_mapping", lambda: None)
    def control(*args):
        calls.append(args)
        if args == ("start", "saha"):
            raise RuntimeError("backend schema gate failed")
    monkeypatch.setattr(cli, "systemctl", control)
    monkeypatch.setattr(cli, "online", lambda: calls.append(("online",)))
    monkeypatch.setattr(sys, "argv", ["saha", "start"])
    with pytest.raises(RuntimeError, match="schema gate"):
        cli.main()
    assert calls == [("stop", "cloudflared"), ("start", "saha")]


def test_build_refuses_when_service_state_cannot_be_verified(cli, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""))
    with pytest.raises(RuntimeError, match="Cannot confirm"):
        cli.build()
    assert list(tmp_path.iterdir()) == []


def test_failed_build_restores_both_previous_builds(cli, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    for app in ("frontend", "admin"):
        output = tmp_path / "apps" / app / ".next"
        output.mkdir(parents=True)
        (output / "BUILD_ID").write_text("original-" + app)
    def run(command, **kwargs):
        if command[0] == "systemctl":
            return SimpleNamespace(returncode=3, stdout="inactive\n")
        if command[0] == "pnpm":
            output = kwargs["cwd"] / ".next"
            output.mkdir()
            (output / "BUILD_ID").write_text("new-build")
            if kwargs["cwd"].name == "admin":
                raise RuntimeError("admin build failed")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(cli.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="admin build failed"):
        cli.build()
    for app in ("frontend", "admin"):
        assert (tmp_path / "apps" / app / ".next/BUILD_ID").read_text() == "original-" + app


@pytest.mark.parametrize("nginx_peer,edge_ip,expected,scheme", [
    ("127.0.0.1", "198.51.100.7", "198.51.100.7", "https"),
    ("192.168.1.20", "1.2.3.4", "192.168.1.20", "http"),
])
async def test_uvicorn_and_application_agree_on_sanitized_proxy_chain(nginx_peer, edge_ip, expected, scheme):
    from starlette.requests import Request
    result = {}
    async def application(scope, receive, send):
        result["ip"] = client_ip(Request(scope))
        result["scheme"] = scope["scheme"]
    scope = {"type": "http", "client": ("127.0.0.1", 1234), "scheme": "http",
             "headers": [(b"x-forwarded-for", nginx_peer.encode()), (b"x-forwarded-proto", scheme.encode()),
                         (b"cf-connecting-ip", edge_ip.encode())]}
    await ProxyHeadersMiddleware(application, trusted_hosts="127.0.0.1,::1")(scope, None, None)
    assert result == {"ip": expected, "scheme": scheme}
