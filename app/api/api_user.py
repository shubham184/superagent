import segment.analytics as analytics
from decouple import config
from fastapi import APIRouter, Depends
from app.models.request import ApiUser as ApiUserRequest
from app.models.response import ApiUser as ApiUserResponse
from app.utils.api import get_current_api_user, handle_exception
from app.utils.prisma import prisma

SEGMENT_WRITE_KEY = config("SEGMENT_WRITE_KEY", None)

router = APIRouter()
analytics.write_key = SEGMENT_WRITE_KEY

@router.post(
    "/api-users",
    name="create",
    description="Create a new API user",
    response_model=ApiUserResponse,
)
async def create(body: ApiUserRequest):
    """Endpoint for creating an agent"""
    try:
        api_user = await prisma.apiuser.create(data={"email": body.email})
        if SEGMENT_WRITE_KEY:
            analytics.identify(api_user.id, {**body.dict()})
            analytics.track(api_user.id, "Signed Up")
        return {"success": True, "data": api_user}
    except Exception as e:
        handle_exception(e)

@router.get(
    "/api-users/me",
    name="get",
    description="Get a single api user",
    response_model=ApiUserResponse,
)
async def get(api_user_info=Depends(get_current_api_user)):
    """Endpoint for getting a single api user"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"id": api_user_info["user_id"]})
        if not api_user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"success": True, "data": api_user}
    except Exception as e:
        handle_exception(e)

@router.delete(
    "/api-users/me",
    name="delete",
    description="Delete an api user",
    response_model=None,
)
async def delete(api_user_info=Depends(get_current_api_user)):
    """Endpoint for deleting an api user"""
    try:
        await prisma.apiuser.delete(where={"id": api_user_info["user_id"]})
        return {"success": True, "data": None}
    except Exception as e:
        handle_exception(e)
