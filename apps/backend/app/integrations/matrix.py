"""Matrix room administration only. No message bodies, device keys or crypto store.

Element performs Olm/Megolm E2EE on members' devices. A dedicated service account
controls membership but must never be used as an Element user or upload keys.
"""
import hashlib
import hmac
from urllib.parse import quote, urlsplit

import httpx
from fastapi import HTTPException

from app.core.config import settings

ALGORITHM = "m.megolm.v1.aes-sha2"


def configured() -> bool:
    urls = [settings.MATRIX_HOMESERVER_URL, settings.ELEMENT_WEB_URL]
    return bool(all(urlsplit(u).scheme == "https" and urlsplit(u).hostname and not urlsplit(u).username and not urlsplit(u).password and not urlsplit(u).query and not urlsplit(u).fragment for u in urls)
                and settings.MATRIX_SERVER_NAME and settings.MATRIX_SERVICE_USER_ID and settings.MATRIX_SERVICE_ACCESS_TOKEN)


def require_configuration() -> None:
    if not configured():
        raise HTTPException(status_code=503, detail="Encrypted chat is not configured. A Saha administrator must connect a Matrix homeserver and Element client. Plaintext chat is disabled.")


async def call(method: str, path: str, *, body: dict | None = None, access_token: str | None = None) -> dict:
    require_configuration()
    # Never follow redirects carrying credentials. No user-supplied destination.
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.request(method, settings.MATRIX_HOMESERVER_URL.rstrip("/") + "/_matrix/client/v3/" + path,
                headers={"Authorization": "Bearer " + (access_token or settings.MATRIX_SERVICE_ACCESS_TOKEN)}, json=body)
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Chat room not found")
        if response.status_code in (401, 403) and access_token:
            raise HTTPException(status_code=401, detail="The Matrix access token could not be verified.")
        if response.is_error or response.is_redirect:
            raise HTTPException(status_code=502, detail="The encrypted chat service could not complete this operation. Please retry.")
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="The encrypted chat service is temporarily unavailable.") from None


async def verify_identity(access_token: str) -> str:
    data = await call("GET", "account/whoami", access_token=access_token)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="The chat service returned an invalid account response.")
    user_id = data.get("user_id", "")
    if not user_id.startswith("@") or ":" not in user_id or user_id.split(":", 1)[1] != settings.MATRIX_SERVER_NAME or user_id == settings.MATRIX_SERVICE_USER_ID:
        raise HTTPException(status_code=422, detail="Link a personal account on the Saha chat homeserver.")
    return user_id


async def assert_keyless_service_account() -> None:
    """Fail closed if someone has used the membership bot as an E2EE client."""
    identity = await call("GET", "account/whoami")
    if not isinstance(identity, dict) or identity.get("user_id") != settings.MATRIX_SERVICE_USER_ID:
        raise HTTPException(status_code=503, detail="The chat membership service account is misconfigured.")
    keys = await call("POST", "keys/query", body={"device_keys": {settings.MATRIX_SERVICE_USER_ID: []}})
    if (not isinstance(keys, dict) or not isinstance(keys.get("device_keys"), dict)
            or keys.get("failures") or keys["device_keys"].get(settings.MATRIX_SERVICE_USER_ID)):
        raise HTTPException(status_code=503, detail="The chat service account must not publish device encryption keys. Contact a Saha administrator.")


def binding(scope: str, scope_id: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"chat:{scope}:{scope_id}".encode(), hashlib.sha256).hexdigest()


def room_configuration(scope: str, scope_id: str) -> dict:
    return {
        "visibility": "private", "preset": "private_chat",
        "room_alias_name": f"saha-{scope}-{scope_id}",
        "name": "Saha private collaboration",
        "creation_content": {"m.federate": False},
        "initial_state": [
            {"type": "m.room.encryption", "state_key": "", "content": {"algorithm": ALGORITHM, "rotation_period_msgs": 100, "rotation_period_ms": 86400000}},
            {"type": "m.room.history_visibility", "state_key": "", "content": {"history_visibility": "joined"}},
            {"type": "m.room.join_rules", "state_key": "", "content": {"join_rule": "invite"}},
            {"type": "org.saha.scope", "state_key": "", "content": {"binding": binding(scope, scope_id)}},
        ],
        "power_level_content_override": {
            "users": {settings.MATRIX_SERVICE_USER_ID: 100}, "users_default": 0,
            "state_default": 100, "events_default": 100, "invite": 100, "kick": 100, "ban": 100,
            "events": {"m.room.encrypted": 0, "m.room.message": 100},
        },
    }


async def inspect_room(room_id: str, scope: str, scope_id: str) -> list[dict]:
    events = await call("GET", "rooms/" + quote(room_id, safe="") + "/state")
    if not isinstance(events, list) or not all(isinstance(e, dict) for e in events):
        raise HTTPException(status_code=502, detail="The chat service returned an invalid room response.")
    state = {(e.get("type"), e.get("state_key", "")): e for e in events}
    def content(name):
        return state.get((name, ""), {}).get("content", {})
    levels = content("m.room.power_levels")
    valid = (content("m.room.encryption").get("algorithm") == ALGORITHM
             and content("m.room.history_visibility").get("history_visibility") == "joined"
             and content("m.room.join_rules").get("join_rule") == "invite"
             and state.get(("m.room.create", ""), {}).get("sender") == settings.MATRIX_SERVICE_USER_ID
             and content("org.saha.scope").get("binding") == binding(scope, scope_id)
             and levels.get("invite") == 100 and levels.get("state_default") == 100
             and levels.get("users") == {settings.MATRIX_SERVICE_USER_ID: 100}
             and levels.get("users_default") == 0
             and levels.get("events_default") == 100
             and levels.get("events", {}).get("m.room.message") == 100
             and levels.get("events", {}).get("m.room.encrypted") == 0)
    if not valid:
        raise HTTPException(status_code=409, detail="This room does not meet Saha's encrypted-chat policy. Contact an administrator.")
    return events


async def ensure_room(scope: str, scope_id: str) -> str:
    alias = f"#saha-{scope}-{scope_id}:{settings.MATRIX_SERVER_NAME}"
    try:
        found = await call("GET", "directory/room/" + quote(alias, safe=""))
        room_id = found["room_id"]
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        result = await call("POST", "createRoom", body=room_configuration(scope, scope_id))
        room_id = result["room_id"]
    await inspect_room(room_id, scope, scope_id)
    return room_id


async def reconcile(room_id: str, scope: str, scope_id: str, allowed: set[str]) -> None:
    events = await inspect_room(room_id, scope, scope_id)
    current = {e["state_key"]: e.get("content", {}).get("membership") for e in events if e.get("type") == "m.room.member"}
    prefix = "rooms/" + quote(room_id, safe="")
    for user_id, membership in current.items():
        if user_id != settings.MATRIX_SERVICE_USER_ID and user_id not in allowed and membership in ("join", "invite"):
            await call("POST", prefix + "/kick", body={"user_id": user_id, "reason": "Saha space membership ended"})
    for user_id in sorted(allowed):
        if current.get(user_id) not in ("join", "invite"):
            await call("POST", prefix + "/invite", body={"user_id": user_id})


def element_url(room_id: str) -> str:
    return settings.ELEMENT_WEB_URL.rstrip("/") + "/#/room/" + quote(room_id, safe="")
