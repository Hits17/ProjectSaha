import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.institutions import render
from app.api.schemas.project import ProjectCreate, ProjectResponse, ProjectStageUpdate, TaskCreate, TaskResponse, TaskUpdate, ReferenceCreate, ReferenceUpdate, ReferenceResponse
from app.core.audit import write_audit_log
from app.core.ratelimit import ANON_READ_LIMIT, WRITE_LIMIT, limiter
from app.core.security import get_optional_user, require_collaborator
from app.db.models.community import Community, CommunityMembership, CommunityVisibility, MembershipRole
from app.db.models.institution import SpacePrivateRecord
from app.db.models.open_resource import OpenResource, OpenResourceStatus
from app.db.models.project import OpenProject, ProjectTask, ProjectReference
from app.db.models.user import User
from app.db.session import get_db
from app.services import communities, institutions

router = APIRouter(prefix="/api/v1/projects", tags=["open-projects"])


async def load(db, project_id, viewer):
    project = await db.get(OpenProject, project_id)
    space = await db.get(Community, project_id)
    if project is None or space is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if viewer is None or not await communities.get_membership(db, project_id, viewer.id):
        raise HTTPException(status_code=404, detail="Project not found")
    return project, space


async def member(db, project_id, actor):
    project, space = await load(db, project_id, actor)
    if not await communities.get_membership(db, project_id, actor.id):
        raise HTTPException(status_code=403, detail="Join this project to contribute.")
    return project, space


async def response(db, project, space, viewer):
    source = await db.get(OpenResource, project.resource_id) if project.resource_id else None
    visible = source is not None and source.is_active and source.status == OpenResourceStatus.APPROVED
    return ProjectResponse(space=await render(db, space, viewer), resource_id=project.resource_id,
        resource_title=source.title if visible else None, source_url=source.source_url if visible else None,
        goal=project.goal, repository_url=project.repository_url, contribution_guide=project.contribution_guide,
        skills_needed=project.skills_needed, stage=project.stage)


@router.get("", response_model=list[ProjectResponse])
@limiter.limit(ANON_READ_LIMIT)
async def browse(
    request: Request, q: str | None = Query(default=None, max_length=200), resource_id: uuid.UUID | None = None,
    offset: int = Query(default=0, ge=0, le=10000), limit: int = Query(default=24, ge=1, le=50),
    db: AsyncSession = Depends(get_db), viewer: User | None = Depends(get_optional_user),
):
    if viewer is None:
        return []
    stmt = select(OpenProject, Community).join(Community, Community.id == OpenProject.community_id).join(CommunityMembership, CommunityMembership.community_id == Community.id).where(CommunityMembership.user_id == viewer.id)
    if resource_id:
        stmt = stmt.where(OpenProject.resource_id == resource_id)
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(Community.name.ilike(pattern, escape="\\"), OpenProject.goal.ilike(pattern, escape="\\")))
    rows = (await db.execute(stmt.order_by(Community.created_at.desc(), Community.id).limit(limit).offset(offset))).all()
    return [await response(db, project, space, viewer) for project, space in rows]


@router.post("", response_model=ProjectResponse, status_code=201)
@limiter.limit(WRITE_LIMIT)
async def create(
    body: ProjectCreate, request: Request, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator),
):
    from app.services.safety import require_public_text
    require_public_text(body.goal + "\n" + (body.contribution_guide or ""), body.name)
    source = await db.get(OpenResource, body.resource_id) if body.resource_id else None
    if body.resource_id and (source is None or not source.is_active or source.status != OpenResourceStatus.APPROVED):
        raise HTTPException(status_code=404, detail="Choose an approved library resource as the project's source.")
    # Creating the workspace, membership, source link and private reference is
    # one DB transaction; a failure cannot leave an orphan community.
    space = Community(name=body.name, slug=await communities._unique_slug(db, body.name),
        description=body.goal, topic=(source.category if source else None) or "general", visibility=CommunityVisibility.PRIVATE,
        created_by=actor.id, is_institution=False, verification_status="unverified")
    db.add(space)
    await db.flush()
    db.add(CommunityMembership(community_id=space.id, user_id=actor.id, role=MembershipRole.OWNER))
    db.add(SpacePrivateRecord(community_id=space.id, reference=institutions.new_reference()))
    project = OpenProject(community_id=space.id, resource_id=source.id if source else None, goal=body.goal,
        repository_url=body.repository_url, contribution_guide=body.contribution_guide,
        skills_needed=body.skills_needed, stage="idea")
    db.add(project)
    await db.commit()
    await db.refresh(space)
    background_tasks.add_task(write_audit_log, action="project.created", user_id=actor.id, resource_type="community", resource_id=space.id, metadata={"resource_id": str(source.id) if source else None})
    return await response(db, project, space, actor)


@router.get("/{project_id}", response_model=ProjectResponse)
@limiter.limit(ANON_READ_LIMIT)
async def detail(project_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), viewer: User | None = Depends(get_optional_user)):
    project, space = await load(db, project_id, viewer)
    return await response(db, project, space, viewer)


@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
@limiter.limit(ANON_READ_LIMIT)
async def tasks(
    project_id: uuid.UUID, request: Request, offset: int = Query(default=0, ge=0, le=10000),
    db: AsyncSession = Depends(get_db), viewer: User | None = Depends(get_optional_user),
):
    await load(db, project_id, viewer)
    return list((await db.execute(select(ProjectTask).where(ProjectTask.project_id == project_id).order_by(ProjectTask.created_at.desc(), ProjectTask.id).limit(50).offset(offset))).scalars().all())


@router.patch("/{project_id}/stage", response_model=ProjectResponse)
@limiter.limit(WRITE_LIMIT)
async def change_stage(
    project_id: uuid.UUID, body: ProjectStageUpdate, request: Request, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator),
):
    project, space = await member(db, project_id, actor)
    communities.require_owner(space, actor.id)
    project.stage = body.stage
    await db.commit()
    background_tasks.add_task(write_audit_log, action="project.stage_updated", user_id=actor.id, resource_type="community", resource_id=project_id, metadata={"stage": body.stage})
    return await response(db, project, space, actor)


@router.post("/{project_id}/tasks", response_model=TaskResponse, status_code=201)
@limiter.limit(WRITE_LIMIT)
async def create_task(
    project_id: uuid.UUID, body: TaskCreate, request: Request, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator),
):
    await member(db, project_id, actor)
    from app.services.safety import require_public_text
    require_public_text(body.description or "", body.title)
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="Task title cannot be blank")
    if body.assigned_to and not await communities.get_membership(db, project_id, body.assigned_to):
        raise HTTPException(status_code=422, detail="Assign tasks only to current project members.")
    task = ProjectTask(project_id=project_id, created_by=actor.id, title=body.title.strip(), description=body.description, assigned_to=body.assigned_to, status="todo", version=1)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    background_tasks.add_task(write_audit_log, action="project.task_created", user_id=actor.id, resource_type="community", resource_id=project_id, metadata={"task_id": str(task.id)})
    if body.assigned_to and body.assigned_to != actor.id:
        from app.services.notifications import notify_best_effort
        background_tasks.add_task(notify_best_effort, body.assigned_to, "project.task_assigned", "You have a new project task",
                                  "A collaborator assigned a task to you.", f"/projects/{project_id}")
    return task


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
@limiter.limit(WRITE_LIMIT)
async def update_task(
    project_id: uuid.UUID, task_id: uuid.UUID, body: TaskUpdate, request: Request, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator),
):
    _, space = await member(db, project_id, actor)
    task = (await db.execute(select(ProjectTask).where(ProjectTask.id == task_id, ProjectTask.project_id == project_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if actor.id not in (space.created_by, task.created_by, task.assigned_to):
        raise HTTPException(status_code=403, detail="Only the task author, assignee or project owner can update it.")
    if task.version != body.version:
        raise HTTPException(status_code=409, detail="This task changed. Reload it before updating.")
    task.status = body.status
    task.version += 1
    await db.commit()
    background_tasks.add_task(write_audit_log, action="project.task_updated", user_id=actor.id, resource_type="community", resource_id=project_id, metadata={"task_id": str(task.id), "status": task.status})
    return task


@router.get("/{project_id}/references", response_model=list[ReferenceResponse])
@limiter.limit(ANON_READ_LIMIT)
async def references(project_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator)):
    await member(db, project_id, actor)
    return list((await db.execute(select(ProjectReference).where(ProjectReference.project_id == project_id).order_by(ProjectReference.pinned.desc(), ProjectReference.created_at.desc(), ProjectReference.id))).scalars().all())


async def reference_permission(db, space, actor, reference=None, *, pin_changed=False):
    membership = await communities.get_membership(db, space.id, actor.id)
    manager = membership is not None and membership.role in (MembershipRole.OWNER, MembershipRole.MODERATOR)
    if (reference is not None and reference.created_by != actor.id and not manager) or (pin_changed and not manager):
        raise HTTPException(status_code=403, detail="Only the link author or a project manager can edit it. Managers control pinned references.")


@router.post("/{project_id}/references", response_model=ReferenceResponse, status_code=201)
@limiter.limit(WRITE_LIMIT)
async def add_reference(project_id: uuid.UUID, body: ReferenceCreate, request: Request, background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator)):
    _, space = await member(db, project_id, actor)
    await reference_permission(db, space, actor, pin_changed=body.pinned)
    # Serialize the quota check for this project without fetching external links.
    await db.execute(select(OpenProject).where(OpenProject.community_id == project_id).with_for_update())
    count = await db.scalar(select(func.count()).select_from(ProjectReference).where(ProjectReference.project_id == project_id))
    if count >= 200:
        raise HTTPException(status_code=409, detail="This project already has 200 references. Remove unused links first.")
    record = ProjectReference(project_id=project_id, created_by=actor.id, **body.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    background_tasks.add_task(write_audit_log, action="project.reference_added", user_id=actor.id, resource_type="community", resource_id=project_id, metadata={"reference_id": str(record.id)})
    return record


async def locked_reference(db, project_id, reference_id):
    record = (await db.execute(select(ProjectReference).where(ProjectReference.project_id == project_id, ProjectReference.id == reference_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Reference not found")
    return record


@router.patch("/{project_id}/references/{reference_id}", response_model=ReferenceResponse)
@limiter.limit(WRITE_LIMIT)
async def update_reference(project_id: uuid.UUID, reference_id: uuid.UUID, body: ReferenceUpdate, request: Request,
                           db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator)):
    _, space = await member(db, project_id, actor)
    record = await locked_reference(db, project_id, reference_id)
    await reference_permission(db, space, actor, record, pin_changed=body.pinned != record.pinned)
    if record.version != body.version:
        raise HTTPException(status_code=409, detail="This reference changed. Reload before editing.")
    for key, value in body.model_dump(exclude={"version"}).items():
        setattr(record, key, value)
    record.version += 1
    await db.commit()
    return record


@router.delete("/{project_id}/references/{reference_id}", status_code=204)
@limiter.limit(WRITE_LIMIT)
async def delete_reference(project_id: uuid.UUID, reference_id: uuid.UUID, request: Request,
                           db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator)):
    _, space = await member(db, project_id, actor)
    record = await locked_reference(db, project_id, reference_id)
    await reference_permission(db, space, actor, record)
    await db.delete(record)
    await db.commit()
