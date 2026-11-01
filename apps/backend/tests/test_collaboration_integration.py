"""Request-level collaboration regressions; never run against a non-test DB.

CI provides PostgreSQL/Redis and initializes the explicit migration chain.
Matrix is not contacted by these cases: only transport retirement is exercised.
"""
import uuid

import pytest
from sqlalchemy import delete, select, text

from app.core.security import hash_password
from app.db.models.community import Community, CommunityMembership, MembershipRole
from app.db.models.open_resource import OpenResource, OpenResourceStatus, OpenResourceType
from app.db.models.user import KYCStatus, User, UserRole
from app.db.models.research import ResearchCollection, SavedResearchSearch
from app.db.session import AsyncSessionLocal

pytestmark = pytest.mark.requires_db


@pytest.fixture
async def actors():
    async with AsyncSessionLocal() as db:
        if await db.scalar(text("SELECT current_database()")) != "saha_test":
            pytest.skip("Collaboration integration fixtures require the isolated saha_test database")
        suffix = uuid.uuid4().hex
        users = {}
        for name in ("owner", "member", "outsider", "admin"):
            actor = User(email=f"{name}-{suffix}@collaboration.invalid", full_name=f"Test {name}",
                hashed_password=hash_password("isolated-test-password-123"), role=UserRole.ADMIN if name == "admin" else UserRole.CREATOR,
                email_verified=True, kyc_status=KYCStatus.PENDING, is_active=True, mfa_enabled=name == "admin")
            db.add(actor)
            users[name] = actor
        await db.commit()
        source = OpenResource(resource_type=OpenResourceType.PATENT, title="Open prototype source for testing",
            summary="Research summary", source_url="https://example.invalid/patent", license="public_domain",
            status=OpenResourceStatus.APPROVED, added_by=users["owner"].id, is_active=True, tags=[])
        db.add(source)
        await db.commit()
        users["source_id"] = source.id
    yield users
    async with AsyncSessionLocal() as db:
        ids = [actor.id for key, actor in users.items() if key != "source_id"]
        await db.execute(delete(ResearchCollection).where(ResearchCollection.owner_id.in_(ids)))
        await db.execute(delete(SavedResearchSearch).where(SavedResearchSearch.owner_id.in_(ids)))
        await db.execute(delete(Community).where(Community.created_by.in_(ids)))
        await db.execute(delete(OpenResource).where(OpenResource.id == users["source_id"]))
        # Audit rows intentionally retain their user references; do not mutate
        # the append-only evidence chain to clean up test identities.
        for actor in (await db.execute(select(User).where(User.id.in_(ids)))).scalars():
            actor.is_active = False
        await db.commit()


async def make_institution(client, headers, name="Open test lab"):
    result = await client.post("/api/v1/institutions", headers=headers,
        json={"name": name, "description": "An open research community", "topic": "general"})
    assert result.status_code == 201, result.text
    return result.json()


async def test_references_are_not_public_member_or_moderator_data(client, actors, auth_header):
    owner = auth_header(actors["owner"].id)
    member = auth_header(actors["member"].id)
    institution = await make_institution(client, owner)
    space_id = institution["id"]
    assert "reference" not in institution
    own = await client.get(f"/api/v1/spaces/{space_id}/private", headers=owner)
    assert own.status_code == 200 and own.json()["reference"].startswith("SP-")
    assert (await client.post(f"/api/v1/communities/{space_id}/join", headers=member)).status_code == 200
    assert (await client.get(f"/api/v1/spaces/{space_id}/private", headers=member)).status_code == 403
    async with AsyncSessionLocal() as db:
        row = await db.scalar(select(CommunityMembership).where(CommunityMembership.community_id == uuid.UUID(space_id), CommunityMembership.user_id == actors["member"].id))
        row.role = MembershipRole.MODERATOR
        await db.commit()
    assert (await client.get(f"/api/v1/spaces/{space_id}/private", headers=member)).status_code == 403
    admin = await client.get(f"/api/v1/spaces/{space_id}/private", headers=auth_header(actors["admin"].id, "admin"))
    assert admin.status_code == 200
    public = await client.get(f"/api/v1/institutions/{space_id}")
    assert public.status_code == 200 and own.json()["reference"] not in public.text


async def test_verification_policy_approval_and_identity_change(client, actors, auth_header):
    owner = auth_header(actors["owner"].id)
    admin = auth_header(actors["admin"].id, "admin")
    space_id = (await make_institution(client, owner))["id"]
    policy = "/api/v1/admin/institutions/policy"
    assert (await client.put(policy, headers=admin, json={"institution_verification_enabled": False})).status_code == 200
    request = {"note": "I represent this institution and provide evidence", "evidence_url": "https://example.invalid/team"}
    assert (await client.post(f"/api/v1/institutions/{space_id}/verification", headers=owner, json=request)).status_code == 409
    assert (await client.put(policy, headers=admin, json={"institution_verification_enabled": True})).status_code == 200
    assert (await client.post(f"/api/v1/institutions/{space_id}/verification", headers=owner, json=request)).status_code == 200
    review = {"decision": "verified", "reason": "Confirmed representation against the official records"}
    assert (await client.post(f"/api/v1/admin/institutions/{space_id}/review", headers=owner, json=review)).status_code == 403
    approved = await client.post(f"/api/v1/admin/institutions/{space_id}/review", headers=admin, json=review)
    assert approved.status_code == 200 and approved.json()["space"]["verification_status"] == "verified"
    # Generic community editor must enforce the same badge invalidation.
    edited = await client.patch(f"/api/v1/communities/{space_id}", headers=owner, json={"name": "Another test institution"})
    assert edited.status_code == 200 and edited.json()["verification_status"] == "unverified"


async def test_confirmed_non_kyc_member_can_post_and_comment_on_institution(client, actors, auth_header):
    owner = auth_header(actors["owner"].id)
    member = auth_header(actors["member"].id)
    space_id = (await make_institution(client, owner))["id"]
    body = {"body": "We are sharing our prototype progress", "visibility": "public", "community_id": space_id}
    assert (await client.post("/api/v1/social", headers=member, json=body)).status_code == 403
    await client.post(f"/api/v1/communities/{space_id}/join", headers=member)
    post = await client.post("/api/v1/social", headers=member, json=body)
    assert post.status_code == 201, post.text
    comment = await client.post(f"/api/v1/social/posts/{post.json()['id']}/comments", headers=owner, json={"body": "I can help with testing"})
    assert comment.status_code == 201, comment.text
    feed = await client.get(f"/api/v1/social/feed?community_id={space_id}")
    assert post.json()["id"] in {p["id"] for p in feed.json()}


async def test_source_linked_project_and_task_permissions_and_versions(client, actors, auth_header):
    owner = auth_header(actors["owner"].id)
    member = auth_header(actors["member"].id)
    outsider = auth_header(actors["outsider"].id)
    project = await client.post("/api/v1/projects", headers=owner, json={
        "name": "Reproducible open prototype", "resource_id": str(actors["source_id"]),
        "goal": "Build and document a reproducible prototype", "skills_needed": ["CAD", "Testing"],
    })
    assert project.status_code == 201, project.text
    project_id = project.json()["space"]["id"]
    path = f"/api/v1/projects/{project_id}/tasks"
    assert (await client.post(path, headers=member, json={"title": "Test prototype"})).status_code == 404
    for name in ("member", "outsider"):
        invited = await client.post(f"/api/v1/communities/{project_id}/members", headers=owner, json={"email": actors[name].email})
        assert invited.status_code == 201, invited.text
    task = await client.post(path, headers=member, json={"title": "Test prototype", "assigned_to": str(actors["member"].id)})
    assert task.status_code == 201, task.text
    task_path = f"{path}/{task.json()['id']}"
    assert (await client.patch(task_path, headers=outsider, json={"version": 1, "status": "done"})).status_code == 403
    assert (await client.patch(task_path, headers=member, json={"version": 1, "status": "done"})).status_code == 200
    assert (await client.patch(task_path, headers=member, json={"version": 1, "status": "todo"})).status_code == 409


async def test_saved_private_posts_and_interactions_follow_membership_revocation(client, actors, auth_header):
    owner = auth_header(actors["owner"].id)
    member = auth_header(actors["member"].id)
    space = await client.post("/api/v1/communities", headers=owner, json={"name": "Private test lab", "topic": "general", "visibility": "private"})
    assert space.status_code == 201, space.text
    space_id = space.json()["id"]
    await client.post(f"/api/v1/communities/{space_id}/members", headers=owner, json={"email": actors["member"].email})
    post = await client.post("/api/v1/social", headers=owner, json={"body": "Private progress update", "visibility": "community", "community_id": space_id})
    assert post.status_code == 201, post.text
    post_id = post.json()["id"]
    assert (await client.post(f"/api/v1/social/posts/{post_id}/save", headers=member)).status_code == 200
    assert (await client.post(f"/api/v1/communities/{space_id}/leave", headers=member)).status_code == 204
    saved = await client.get("/api/v1/social/saved", headers=member)
    assert post_id not in {p["id"] for p in saved.json()}
    assert (await client.get(f"/api/v1/social/posts/{post_id}", headers=member)).status_code == 404
    assert (await client.post(f"/api/v1/social/posts/{post_id}/vote", headers=member, json={"value": 1})).status_code == 404


async def test_legacy_chat_cannot_receive_new_plaintext(client, actors, auth_header):
    owner = auth_header(actors["owner"].id)
    space_id = (await make_institution(client, owner))["id"]
    result = await client.post(f"/api/v1/communities/{space_id}/messages", headers=owner, json={"content": "Do not persist this message"})
    assert result.status_code == 410
    async with AsyncSessionLocal() as db:
        from app.db.models.community import CommunityMessage
        assert await db.scalar(select(CommunityMessage.id).where(CommunityMessage.community_id == uuid.UUID(space_id))) is None


async def test_research_collections_and_searches_are_owner_only_and_resaves_preserve_notes(client, actors, auth_header):
    owner = auth_header(actors["owner"].id)
    outsider = auth_header(actors["outsider"].id)
    admin = auth_header(actors["admin"].id, "admin")
    collection = await client.post("/api/v1/research/collections", headers=owner, json={"name": "Private battery research"})
    assert collection.status_code == 201, collection.text
    collection_id = collection.json()["id"]
    path = f"/api/v1/research/collections/{collection_id}/items"
    assert (await client.get(path, headers=outsider)).status_code == 404
    assert (await client.get(path, headers=admin)).status_code == 404
    resource_path = f"{path}/{actors['source_id']}"
    assert (await client.put(resource_path, headers=owner, json={"note": "Keep this original private note"})).status_code == 204
    assert (await client.put(resource_path, headers=owner, json={})).status_code == 204
    saved = await client.get(path, headers=owner)
    assert saved.status_code == 200 and saved.json()[0]["note"] == "Keep this original private note"
    assert (await client.put(resource_path, headers=outsider, json={"note": "Replace note"})).status_code == 404
    assert (await client.post("/api/v1/research/searches", headers=owner, json={"label": "Batteries", "query": "battery recycling", "resource_type": "patent"})).status_code == 204
    searches = await client.get("/api/v1/research/searches", headers=owner)
    assert len(searches.json()) == 1
    search_id = searches.json()[0]["id"]
    assert (await client.get("/api/v1/research/searches", headers=outsider)).json() == []
    await client.delete(f"/api/v1/research/searches/{search_id}", headers=outsider)
    assert len((await client.get("/api/v1/research/searches", headers=owner)).json()) == 1


async def test_notification_cursor_drains_equal_timestamp_batches_without_loss(actors):
    from datetime import datetime, timezone
    from app.db.models.notification import Notification
    from app.services.notifications import fetch_since
    stamp = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        rows = [Notification(user_id=actors["owner"].id, type="project.task_assigned", title=f"Task {i}", created_at=stamp) for i in range(60)]
        db.add_all(rows)
        await db.commit()
        first = await fetch_since(db, actors["owner"].id, stamp, uuid.UUID(int=0))
        assert len(first) == 50
        second = await fetch_since(db, actors["owner"].id, first[-1].created_at, first[-1].id)
        assert len(second) == 10
        assert len({n.id for n in first + second}) == 60


async def test_standalone_project_references_and_invite_only_boundary(client, actors, auth_header):
    owner = auth_header(actors["owner"].id)
    member = auth_header(actors["member"].id)
    project = await client.post("/api/v1/projects", headers=owner, json={"name": "Independent team", "goal": "Build something useful together"})
    assert project.status_code == 201, project.text
    assert project.json()["resource_id"] is None
    assert project.json()["space"]["visibility"] == "private"
    pid = project.json()["space"]["id"]
    base = f"/api/v1/projects/{pid}"
    assert (await client.get(base)).status_code == 404
    assert (await client.get(base, headers=member)).status_code == 404
    assert (await client.get("/api/v1/projects", headers=member)).json() == []
    assert (await client.post(f"/api/v1/communities/{pid}/join", headers=member)).status_code == 403
    assert (await client.patch(f"/api/v1/communities/{pid}", headers=owner, json={"visibility": "public"})).status_code == 422
    assert (await client.post(f"/api/v1/communities/{pid}/members", headers=owner, json={"email": actors["member"].email})).status_code == 201
    assert (await client.get(base, headers=member)).status_code == 200
    body = {"title": "Prototype CAD", "url": "https://example.org/design", "platform": "other", "file_type": "design", "pinned": True}
    assert (await client.post(base + "/references", headers=member, json=body)).status_code == 403
    result = await client.post(base + "/references", headers=owner, json=body)
    assert result.status_code == 201, result.text
    link = base + "/references/" + result.json()["id"]
    assert (await client.patch(link, headers=member, json={**body, "version": 1})).status_code == 403
    assert (await client.patch(link, headers=owner, json={**body, "title": "Latest CAD", "version": 1})).status_code == 200
    assert (await client.patch(link, headers=owner, json={**body, "version": 1})).status_code == 409
    assert (await client.get(base + "/references", headers=member)).json()[0]["title"] == "Latest CAD"
    assert (await client.post(f"/api/v1/communities/{pid}/leave", headers=member)).status_code == 204
    assert (await client.get(base + "/references", headers=member)).status_code == 404
    assert (await client.delete(link, headers=owner)).status_code == 204
