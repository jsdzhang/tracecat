from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import NoResultFound
from sqlmodel import select

from tracecat.auth.dependencies import WorkspaceUserRole
from tracecat.db.dependencies import AsyncDBSession
from tracecat.db.schemas import Action
from tracecat.workflow.actions.models import (
    ActionControlFlow,
    ActionCreate,
    ActionRead,
    ActionReadMinimal,
    ActionUpdate,
)

router = APIRouter(prefix="/actions")


@router.get("", tags=["actions"])
async def list_actions(
    role: WorkspaceUserRole,
    workflow_id: str,
    session: AsyncDBSession,
) -> list[ActionReadMinimal]:
    """List all actions for a workflow."""
    statement = select(Action).where(
        Action.owner_id == role.workspace_id,
        Action.workflow_id == workflow_id,
    )
    results = await session.exec(statement)
    actions = results.all()
    action_metadata = [
        ActionReadMinimal(
            id=action.id,
            workflow_id=workflow_id,
            type=action.type,
            title=action.title,
            description=action.description,
            status=action.status,
        )
        for action in actions
    ]
    return action_metadata


@router.post("", tags=["actions"])
async def create_action(
    role: WorkspaceUserRole,
    params: ActionCreate,
    session: AsyncDBSession,
) -> ActionReadMinimal:
    """Create a new action for a workflow."""
    action = Action(
        owner_id=role.workspace_id,
        workflow_id=params.workflow_id,
        type=params.type,
        title=params.title,
        description="",  # Default to empty string
    )
    # Check if a clashing action ref exists
    statement = select(Action).where(
        Action.owner_id == role.workspace_id,
        Action.workflow_id == action.workflow_id,
        Action.ref == action.ref,
    )
    result = await session.exec(statement)
    if result.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Action ref already exists in the workflow",
        )

    session.add(action)
    await session.commit()
    await session.refresh(action)

    action_metadata = ActionReadMinimal(
        id=action.id,
        workflow_id=params.workflow_id,
        type=params.type,
        title=action.title,
        description=action.description,
        status=action.status,
    )
    return action_metadata


@router.get("/{action_id}", tags=["actions"])
async def get_action(
    role: WorkspaceUserRole,
    action_id: str,
    workflow_id: str,
    session: AsyncDBSession,
) -> ActionRead:
    """Get an action."""
    statement = select(Action).where(
        Action.owner_id == role.workspace_id,
        Action.id == action_id,
        Action.workflow_id == workflow_id,
    )
    result = await session.exec(statement)
    try:
        action = result.one()
    except NoResultFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        ) from e

    return ActionRead(
        id=action.id,
        type=action.type,
        title=action.title,
        description=action.description,
        status=action.status,
        inputs=action.inputs,
        control_flow=ActionControlFlow(**action.control_flow),
    )


@router.post("/{action_id}", tags=["actions"])
async def update_action(
    role: WorkspaceUserRole,
    action_id: str,
    params: ActionUpdate,
    session: AsyncDBSession,
) -> ActionRead:
    """Update an action."""
    # Fetch the action by id
    statement = select(Action).where(
        Action.owner_id == role.workspace_id,
        Action.id == action_id,
    )
    result = await session.exec(statement)
    try:
        action = result.one()
    except NoResultFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        ) from e

    if params.title is not None:
        action.title = params.title
    if params.description is not None:
        action.description = params.description
    if params.status is not None:
        action.status = params.status
    if params.inputs is not None:
        action.inputs = params.inputs
    if params.control_flow is not None:
        action.control_flow = params.control_flow.model_dump(mode="json")

    session.add(action)
    await session.commit()
    await session.refresh(action)

    return ActionRead(
        id=action.id,
        type=action.type,
        title=action.title,
        description=action.description,
        status=action.status,
        inputs=action.inputs,
    )


@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["actions"])
async def delete_action(
    role: WorkspaceUserRole,
    action_id: str,
    session: AsyncDBSession,
) -> None:
    """Delete an action."""
    statement = select(Action).where(
        Action.owner_id == role.workspace_id,
        Action.id == action_id,
    )
    result = await session.exec(statement)
    try:
        action = result.one()
    except NoResultFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        ) from e
    # If the user doesn't own this workflow, they can't delete the action
    await session.delete(action)
    await session.commit()
