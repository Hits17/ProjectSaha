# Private chat: Matrix/Element E2EE

Updated 2026-11-01: standalone invite-only projects use the existing `community` room scope. The deployment choice remains **local testing only**; no real two-device acceptance is claimed. See [Current status](CURRENT-STATUS.md).

## Security boundary

Saha coordinates space membership. Element encrypts/decrypts on participant devices using Matrix Olm/Megolm. Saha's Matrix integration performs account ownership checks, room creation, state inspection, invitations and kicks. It has no message-read/send API, device private keys, crypto store or plaintext message table for the new transport.

The dedicated service account is a **membership administrator**, not a conversation participant with encryption keys. Never sign into Element using it and never upload device keys for it. Saha checks the service identity and rejects an account with uploaded device keys before preparing a room. Keep its token separate from personal accounts. It can see room metadata and change membership; platform administration is therefore still trusted for membership. Members should verify each other's devices and review membership changes in Element.

Rooms are private, invite-only, non-federated and use `m.megolm.v1.aes-sha2`, joined-only history and bounded session rotation settings. Power levels prohibit normal participants from sending `m.room.message` plaintext, changing room state or inviting other accounts. Normal participants can send `m.room.encrypted`. Saha checks the encrypted-room policy before returning a link. Room aliases are deterministic for retry recovery, but recovered rooms must match the configured creator and Saha scope binding. No private space reference is included in room metadata.

Saha does not claim that TLS or its legacy AES-at-rest implementation is E2EE. Old community/proposal chat routes now return 410 and no longer read/decrypt/write message contents. Historical records remain unchanged; deployment must decide retention/export separately. Old messages are not copied into encrypted rooms.

Public institution posts and public-audience comments remain public discussion. Project tasks and reference metadata are private to invited members but are not E2EE. Do not enter secrets that require encrypted chat into those fields. E2EE also means server-side contact scanning and invisible content moderation of private messages are not possible. Support participant-submitted reports instead.

## Setup required before deployment

1. Operate a maintained Matrix homeserver and Element Web client behind HTTPS, using trusted origins. The optional templates in `saha-dev-infra/chat/` can prepare a dedicated deployment. Pin reviewed image versions/digests and back up both database and configuration/signing keys. Do not expose unauthenticated registration.
2. Create a dedicated non-personal Matrix service account, without crypto/device keys. Its only purpose is to administer Saha rooms. Create personal accounts through your chosen registration/SSO policy.
3. Set these backend variables (all are required for configured chat):

   ```dotenv
   MATRIX_HOMESERVER_URL=https://matrix.example.org
   MATRIX_SERVER_NAME=matrix.example.org
   MATRIX_SERVICE_USER_ID=@saha-service:matrix.example.org
   MATRIX_SERVICE_ACCESS_TOKEN=<dedicated service token>
   ELEMENT_WEB_URL=https://chat.example.org
   ```

4. Apply the new migrations in `OPEN-COLLABORATION-DEPLOYMENT.md` before restarting the application. Deploy backend and frontend together: old message endpoints deliberately stop working, and the new interface must be present. No such live deployment has been performed by this development session.
5. A member opens a project/community/proposal secure-chat panel, signs into their personal Element account, and links it using an account access token plus a fresh Saha password/MFA step-up. Saha sends this token only to the fixed configured homeserver's `whoami` endpoint, then discards it. It stores only the verified Matrix user ID. Never send a password, recovery key or encryption key to Saha.
6. For this initial integration, link an account on the configured homeserver. A Matrix account can link to only one Saha identity. Relinking to a different Matrix account is deliberately blocked until an audited migration revokes the former account in every room. Do not work around this by editing DB rows.
7. “Prepare secure conversation” checks Saha participation, reconciles allowed linked Matrix accounts and opens Element. Participants accept invitations and verify devices there. The chat interface currently lives in Element, not an embedded Saha timeline. This is an explicit initial integration tradeoff, not an assertion that an embedded chat client is already complete.

## Membership/recovery behavior

- Public page membership alone never publishes chat. Only members with linked personal chat accounts are invited.
- Leaving/removal revokes existing Matrix room membership before confirming the Saha removal. If Matrix is unavailable, removal fails closed and must be retried. Account deactivation also revokes external rooms before confirmation. Metadata administration is currently serialized to avoid revoke/invite races; message traffic bypasses Saha entirely.
- New room opens reconcile active participants and reject policy-mismatched rooms. Monitor failures and support recovery rather than silently falling back to plaintext.
- Removal cannot revoke knowledge or plaintext already received by a device. The Matrix client must rotate outbound encryption sessions when membership changes. Verify this with real clients before launch.
- Key recovery uses Element's recovery/device verification, not a Saha administrator master decryption key. Losing all devices and recovery material can lose access to encrypted history. Account access tokens and key recovery material are different things.
- Room alias recovery is bound to `SECRET_KEY`; changing that key requires an explicit chat binding migration/reconciliation. Do not rotate it without planning room recovery.

## Required two-device acceptance run

Use test accounts and non-sensitive messages on an isolated homeserver. Do not treat mocks as encryption certification.

1. Link two distinct personal accounts, join a space and open the room from both clients. Verify devices.
2. Send unique test text and an attachment in Element. Inspect the homeserver event representation: event type is `m.room.encrypted`; no message/attachment plaintext is present. Confirm the Saha database/logs contain neither.
3. A normal participant attempting `m.room.message` or an invitation must be denied by room power levels.
4. Remove one Saha member, confirm Matrix kick, send fresh messages and prove the removed device cannot decrypt them. Test concurrent open/removal and a provider outage.
5. Join a third account, inspect pre-join history behavior and confirm it cannot obtain inappropriate old keys. Inspect Element's sharing/verification prompts.
6. Exercise a second device, device verification, recovery and loss of recovery material. Ensure no server-side recovery key has been introduced.
7. Test duplicate room preparation, service timeout, room state tampering, account deactivation and reactivation. Do not enable ordinary chat until all checks pass.

These live checks are **pending** because this session has no configured homeserver and cannot open local sockets. Tests currently verify the adapter/policy with mocks and the database schema offline.

## Local test choice

The owner selected **local testing only**. A dedicated, statically validated
setup is prepared in `saha-dev-infra/local-checks/`; see its README. It uses local
TLS verification with a private test CA, separate test databases and the temporary
Matrix realm `saha-chat.localhost`. No production identity/domain is selected.
Docker/socket permissions still prevent starting it from this agent session.
The live acceptance list above remains pending.
