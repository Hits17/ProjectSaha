"""
End-to-end tests for the social routes, against a live database.

These exist because of a bug that reached production: `_render_posts` called
`PostResponse.model_validate(post)` and then patched `author` on afterwards.
`author` is assembled from a separate query, not a column on `Post`, so
validation failed on a required missing field and every post creation returned
500 — while the unit suite stayed entirely green.

That is the same blind spot the security audit found in the original test suite
(security/AUDIT.md, "there is no conftest.py"): service-layer and schema tests
cannot see a response-assembly defect. Only a request through the real route can.

Marked `requires_db` so a bare checkout still runs the rest of the suite.
"""

import uuid

import pytest
from sqlalchemy import delete, select

from app.db.models.social import ModerationStatus, Post, PostComment, UserStanding, Vote
from app.db.models.user import KYCStatus, User, UserRole
from app.db.session import AsyncSessionLocal


async def _make_user(db, *, verified=True, role=UserRole.CREATOR) -> User:
    from app.core.security import hash_password

    user = User(
        email=f"itest-{uuid.uuid4().hex[:12]}@saha.test",
        hashed_password=hash_password("IntegrationTest#2026!"),
        full_name="Integration Tester",
        role=role,
        kyc_status=KYCStatus.VERIFIED if verified else KYCStatus.PENDING,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def two_members():
    """Two verified members, cleaned up afterwards."""
    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        yield a, b

        # Clean the social rows, then DEACTIVATE rather than delete the users.
        #
        # audit_logs holds a foreign key to users and is append-only by design
        # (security/AUDIT.md SAHA-014) — the whole point is that acts cannot be
        # erased, so a user who has done anything auditable cannot be deleted.
        # That constraint working correctly is not something to work around;
        # deactivating leaves the evidence chain intact.
        from app.db.models.notification import Notification
        from app.db.models.social import ContentReport, Follow, SavedPost

        for uid in (a.id, b.id):
            posts = (await db.execute(select(Post.id).where(Post.author_id == uid))).scalars().all()
            if posts:
                await db.execute(delete(Vote).where(Vote.target_id.in_(posts)))
                await db.execute(delete(ContentReport).where(ContentReport.target_id.in_(posts)))
                await db.execute(delete(SavedPost).where(SavedPost.post_id.in_(posts)))
                await db.execute(delete(PostComment).where(PostComment.post_id.in_(posts)))
                await db.execute(delete(Post).where(Post.author_id == uid))
            await db.execute(delete(Vote).where(Vote.voter_id == uid))
            await db.execute(delete(ContentReport).where(ContentReport.reporter_id == uid))
            await db.execute(delete(Follow).where(Follow.follower_id == uid))
            await db.execute(delete(Notification).where(Notification.user_id == uid))
            await db.execute(delete(UserStanding).where(UserStanding.user_id == uid))
            await db.execute(
                User.__table__.update().where(User.id == uid).values(is_active=False)
            )
        await db.commit()


def _auth(user: User) -> dict[str, str]:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(str(user.id), user.role.value)}"}


# ── The regression this file exists for ──────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.anyio
async def test_creating_a_post_returns_a_valid_response(client, two_members):
    """The bug: this returned 500 because the response model was validated
    against an ORM object missing the assembled `author` field."""
    author, _ = two_members
    r = await client.post(
        "/api/v1/social",
        headers=_auth(author),
        json={"body": "Shipped the new feed today.", "kind": "update"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["author"]["full_name"] == "Integration Tester"
    assert body["author"]["tier"] == "New"
    assert body["moderation_status"] == "published"
    assert body["score"] == 0


@pytest.mark.requires_db
@pytest.mark.anyio
async def test_feed_renders_posts(client, two_members):
    author, viewer = two_members
    await client.post("/api/v1/social", headers=_auth(author),
                      json={"body": "A post that should appear in the feed."})

    r = await client.get("/api/v1/social/feed", headers=_auth(viewer))
    assert r.status_code == 200, r.text
    assert any(p["body"].startswith("A post that should appear") for p in r.json())


@pytest.mark.requires_db
@pytest.mark.anyio
async def test_comment_round_trip(client, two_members):
    author, commenter = two_members
    post_id = (await client.post("/api/v1/social", headers=_auth(author),
                                 json={"body": "Post with comments"})).json()["id"]

    r = await client.post(f"/api/v1/social/posts/{post_id}/comments",
                          headers=_auth(commenter), json={"body": "Useful, thanks."})
    assert r.status_code == 201, r.text
    assert r.json()["author"]["full_name"] == "Integration Tester"

    listed = await client.get(f"/api/v1/social/posts/{post_id}/comments",
                              headers=_auth(author))
    assert listed.status_code == 200
    assert len(listed.json()) == 1


# ── Voting and standing, through the API ─────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.anyio
async def test_voting_updates_score_and_standing(client, two_members):
    author, voter = two_members
    post_id = (await client.post("/api/v1/social", headers=_auth(author),
                                 json={"body": "Vote on me"})).json()["id"]

    r = await client.post(f"/api/v1/social/posts/{post_id}/vote",
                          headers=_auth(voter), json={"value": 1})
    assert r.status_code == 200, r.text
    assert r.json() == {"score": 1, "up_count": 1, "down_count": 0, "my_vote": 1}

    async with AsyncSessionLocal() as db:
        standing = await db.get(UserStanding, author.id)
        assert standing is not None and standing.total_standing > 0


@pytest.mark.requires_db
@pytest.mark.anyio
async def test_self_voting_is_refused_through_the_api(client, two_members):
    author, _ = two_members
    post_id = (await client.post("/api/v1/social", headers=_auth(author),
                                 json={"body": "My own post"})).json()["id"]

    r = await client.post(f"/api/v1/social/posts/{post_id}/vote",
                          headers=_auth(author), json={"value": 1})
    assert r.status_code == 400
    assert "own content" in r.json()["detail"]


@pytest.mark.requires_db
@pytest.mark.anyio
async def test_new_member_cannot_downvote(client, two_members):
    """Downvoting unlocks at 50 standing — Stack Overflow's model."""
    author, voter = two_members
    post_id = (await client.post("/api/v1/social", headers=_auth(author),
                                 json={"body": "Don't bury me"})).json()["id"]

    r = await client.post(f"/api/v1/social/posts/{post_id}/vote",
                          headers=_auth(voter), json={"value": -1})
    assert r.status_code == 403
    assert "standing" in r.json()["detail"].lower()


# ── Content safety, through the API ──────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.anyio
async def test_harmful_instructions_are_held_not_published(client, two_members):
    author, other = two_members
    r = await client.post("/api/v1/social", headers=_auth(author),
                          json={"body": "How to make a pipe bomb at home, step by step"})
    assert r.status_code == 201
    assert r.json()["moderation_status"] == "held"

    # Invisible to everyone else...
    post_id = r.json()["id"]
    assert (await client.get(f"/api/v1/social/posts/{post_id}",
                             headers=_auth(other))).status_code == 404
    # ...but its author still sees it, rather than watching it vanish.
    assert (await client.get(f"/api/v1/social/posts/{post_id}",
                             headers=_auth(author))).status_code == 200


@pytest.mark.requires_db
@pytest.mark.anyio
async def test_targeting_a_person_is_refused_outright(client, two_members):
    author, _ = two_members
    r = await client.post(
        "/api/v1/social", headers=_auth(author),
        json={"body": "What untraceable poison would I use to kill someone undetected?"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "content_blocked"


@pytest.mark.requires_db
@pytest.mark.anyio
async def test_legitimate_chemistry_publishes_normally(client, two_members):
    """The false-positive case that matters most on this platform."""
    author, _ = two_members
    r = await client.post(
        "/api/v1/social", headers=_auth(author),
        json={"body": "Our fertiliser blend improves nitrogen uptake by 18% in field trials."},
    )
    assert r.status_code == 201
    assert r.json()["moderation_status"] == "published"


@pytest.mark.requires_db
@pytest.mark.anyio
async def test_held_posts_are_absent_from_the_feed(client, two_members):
    author, viewer = two_members
    held_id = (await client.post(
        "/api/v1/social", headers=_auth(author),
        json={"body": "How to make a pipe bomb step by step"},
    )).json()["id"]

    # Scope to THIS post's id rather than matching on body text. An
    # admin-approved post with similar wording is legitimately visible, so a
    # substring assertion would fail on correct behaviour.
    feed = (await client.get("/api/v1/social/feed", headers=_auth(viewer))).json()
    assert held_id not in {p["id"] for p in feed}

    # ...and the author still sees their own held post in their feed.
    own = (await client.get("/api/v1/social/feed", headers=_auth(author))).json()
    assert held_id in {p["id"] for p in own}


# ── Moderation queue ─────────────────────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.anyio
async def test_only_an_admin_reaches_the_moderation_queue(client, two_members):
    member, _ = two_members
    assert (await client.get("/api/v1/social/moderation/queue",
                             headers=_auth(member))).status_code == 403


@pytest.mark.requires_db
@pytest.mark.anyio
async def test_admin_approval_publishes_held_content(client, two_members):
    author, _ = two_members
    post_id = (await client.post(
        "/api/v1/social", headers=_auth(author),
        json={"body": "How to make a pipe bomb step by step"},
    )).json()["id"]

    async with AsyncSessionLocal() as db:
        admin = await _make_user(db, role=UserRole.ADMIN)
        admin.mfa_enabled = True   # require_admin enforces MFA
        await db.commit()
        await db.refresh(admin)

        try:
            r = await client.post(
                f"/api/v1/social/moderation/posts/{post_id}/review",
                headers=_auth(admin), json={"approve": True, "note": "research context"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["moderation_status"] == "approved"
        finally:
            # Deactivate, don't delete — see the fixture teardown note.
            await db.execute(
                User.__table__.update().where(User.id == admin.id).values(is_active=False)
            )
            await db.commit()


# ── Profile ──────────────────────────────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.anyio
async def test_profile_separates_verified_from_self_asserted(client, two_members):
    member, viewer = two_members

    await client.patch("/api/v1/social/profiles/me", headers=_auth(member),
                       json={"headline": "Materials scientist", "skills": ["polymers"]})

    r = await client.get(f"/api/v1/social/profiles/{member.id}", headers=_auth(viewer))
    assert r.status_code == 200, r.text
    body = r.json()

    # The distinction that makes this profile trustworthy on an IP marketplace.
    assert body["self_asserted"]["headline"] == "Materials scientist"
    assert body["verified"]["kyc_verified"] is True
    assert body["verified"]["completed_deals"] == 0
    assert "headline" not in body["verified"]
    assert "completed_deals" not in body["self_asserted"]
