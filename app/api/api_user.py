import segment.analytics as analytics
from decouple import config
from fastapi import APIRouter, Depends, HTTPException
from app.models.request import ApiUser as ApiUserRequest
from app.models.response import ApiUser as ApiUserResponse
from app.utils.api import get_current_api_user, handle_exception, get_keycloak_user_id
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
async def get_or_create_user(keycloak_user_id=Depends(get_keycloak_user_id)):
    # Check if the user exists in the local database
    existing_user = await prisma.apiuser.find_unique(where={"keycloakUserId": keycloak_user_id})

    # If user exists, return user data
    if existing_user:
        return {"success": True, "data": existing_user}

    # If user does not exist, create a new record
    new_user = await prisma.apiuser.create(data={
        "keycloakUserId": keycloak_user_id,
        # Add other user information here if necessary
    })

    # If you are using Segment, send the analytics data
    if SEGMENT_WRITE_KEY:
        analytics.identify(new_user.id, {"keycloakUserId": new_user.keycloakUserId})
        analytics.track(new_user.id, "Signed Up")

    return {"success": True, "data": new_user}



@router.get(
    "/api-users/me",
    name="get",
    description="Get the current API user",
    response_model=ApiUserResponse,
)
async def get(api_user_info=Depends(get_keycloak_user_id)):  # Renamed for clarity
    """Endpoint for getting the current API user linked to the Keycloak account."""
    try:
        # If `api_user_info` is an instance of `ApiUser`:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_info})
        if not api_user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"success": True, "data": api_user}
    except Exception as e:
        handle_exception(e)


@router.delete(
    "/api-users/me",
    name="delete",
    description="Delete the current API user",
    response_model=None,
)
async def delete(api_user_info=Depends(get_keycloak_user_id)):
    """Endpoint for deleting the current API user."""
    try:
        await prisma.apiuser.delete(where={"keycloakUserId": api_user_info})
        return {"success": True, "message": "User deleted successfully"}
    except Exception as e:
        handle_exception(e)
