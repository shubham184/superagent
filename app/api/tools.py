import json

import segment.analytics as analytics
from decouple import config
from fastapi import APIRouter, Depends, HTTPException

from app.models.request import Tool as ToolRequest
from app.models.response import (
    Tool as ToolResponse,
)
from app.models.response import (
    ToolList as ToolListResponse,
)
from app.utils.api import get_current_api_user, handle_exception, get_keycloak_user_id # modified
from app.utils.prisma import prisma

SEGMENT_WRITE_KEY = config("SEGMENT_WRITE_KEY", None)

router = APIRouter()
analytics.write_key = SEGMENT_WRITE_KEY


@router.post(
    "/tools",
    name="create",
    description="Create a new tool",
    response_model=ToolResponse,
)
async def create(
    body: ToolRequest,
    api_user_id=Depends(get_keycloak_user_id) # modified
):
    """Endpoint for creating an tool"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        
        if SEGMENT_WRITE_KEY:
            analytics.track(api_user.id, "Created Tool")
        body.metadata = json.dumps(body.metadata) if body.metadata else ""
        data = await prisma.tool.create({**body.dict(), "apiUserId": api_user.id})
        return {"success": True, "data": data}
    except Exception as e:
        handle_exception(e)


@router.get(
    "/tools",
    name="list",
    description="List all tools",
    response_model=ToolListResponse,
)
async def list(api_user_id=Depends(get_keycloak_user_id)): # modified
    """Endpoint for listing all tools"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        
        data = await prisma.tool.find_many(
            where={"apiUserId": api_user.id}, order={"createdAt": "desc"}
        )
        return {"success": True, "data": data}
    except Exception as e:
        handle_exception(e)


@router.get(
    "/tools/{tool_id}",
    name="get",
    description="Get a specific tool",
    response_model=ToolResponse,
)
async def get(tool_id: str, api_user_id=Depends(get_keycloak_user_id)): # modified
    """Endpoint for getting a specific tool"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        
        data = await prisma.tool.find_first(
            where={"id": tool_id, "apiUserId": api_user.id}
        )
        return {"success": True, "data": data}
    except Exception as e:
        handle_exception(e)


@router.patch(
    "/tools/{tool_id}",
    name="update",
    description="Update a specific tool",
    response_model=ToolResponse,
)
async def update(
    tool_id: str, body: ToolRequest, api_user_id=Depends(get_keycloak_user_id) # modified and I had a try/except block here
):
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        """Endpoint for updating a specific tool"""
        if SEGMENT_WRITE_KEY:
            analytics.track(api_user.id, "Updated Tool")
        body.metadata = json.dumps(body.metadata) if body.metadata else ""
        data = await prisma.tool.update(
            where={"id": tool_id},
            data={
                **body.dict(),
                "apiUserId": api_user.id,
            },
        )
        return {"success": True, "data": data}
    except Exception as e:
        handle_exception(e)


@router.delete(
    "/tools/{tool_id}",
    name="delete",
    description="Delete a specific tool",
)
async def delete(tool_id: str, api_user_id=Depends(get_keycloak_user_id)): # modified
    """Endpoint for deleting a specific tool"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        
        if SEGMENT_WRITE_KEY:
            analytics.track(api_user.id, "Deleted Tool")
        await prisma.agenttool.delete_many(where={"toolId": tool_id})
        await prisma.tool.delete(where={"id": tool_id})
        return {"success": True, "data": None}
    except Exception as e:
        handle_exception(e)
