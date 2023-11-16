import asyncio
import json

import segment.analytics as analytics
from decouple import config
from fastapi import APIRouter, Depends, HTTPException # added

from app.datasource.flow import vectorize_datasource
from app.models.request import Datasource as DatasourceRequest
from app.models.response import (
    Datasource as DatasourceResponse,
)
from app.models.response import (
    DatasourceList as DatasourceListResponse,
)
from app.utils.api import get_current_api_user, handle_exception, get_keycloak_user_id
from app.utils.prisma import prisma
from prisma.models import Datasource

SEGMENT_WRITE_KEY = config("SEGMENT_WRITE_KEY", None)
account_name = config("AZURE_STORAGE_ACCOUNT_NAME")
account_key = config("AZURE_STORAGE_ACCOUNT_KEY")

router = APIRouter()
analytics.write_key = SEGMENT_WRITE_KEY


@router.post(
    "/datasources",
    name="create",
    description="Create a new datasource",
    response_model=DatasourceResponse,
)
async def create(
    body: DatasourceRequest,
    api_user_id=Depends(get_keycloak_user_id) # modified
):
    """Endpoint for creating an datasource"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        
        if body.metadata:
            body.metadata = json.dumps(body.metadata)

        if SEGMENT_WRITE_KEY:
            analytics.track(api_user.id, "Created Datasource")
        data = await prisma.datasource.create({**body.dict(), "apiUserId": api_user.id})

        async def run_vectorize_flow(datasource: Datasource):
            try:
                await vectorize_datasource(
                    datasource=datasource,
                )
            except Exception as flow_exception:
                handle_exception(flow_exception)

        asyncio.create_task(run_vectorize_flow(datasource=data))
        return {"success": True, "data": data}
    except Exception as e:
        handle_exception(e)


@router.get(
    "/datasources",
    name="list",
    description="List all datasources",
    response_model=DatasourceListResponse,
)
async def list(api_user_id=Depends(get_keycloak_user_id)): # modified
    """Endpoint for listing all datasources"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        
        data = await prisma.datasource.find_many(
            where={"apiUserId": api_user.id}, order={"createdAt": "desc"}
        )
        return {"success": True, "data": data}
    except Exception as e:
        handle_exception(e)


@router.get(
    "/datasources/{datasource_id}",
    name="get",
    description="Get a specific datasource",
    response_model=DatasourceResponse,
)
async def get(datasource_id: str, api_user_id=Depends(get_keycloak_user_id)): # modified
    """Endpoint for getting a specific datasource"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        
        data = await prisma.datasource.find_first(
            where={"id": datasource_id, "apiUserId": api_user.id}
        )
        return {"success": True, "data": data}
    except Exception as e:
        handle_exception(e)


@router.patch(
    "/datasources/{datasource_id}",
    name="update",
    description="Update a specific datasource",
    response_model=DatasourceResponse,
)
async def update(
    datasource_id: str, body: DatasourceRequest, api_user_id=Depends(get_keycloak_user_id) # modified
):
    """Endpoint for updating a specific datasource"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        
        if SEGMENT_WRITE_KEY:
            analytics.track(api_user.id, "Updated Datasource")
        data = await prisma.datasource.update(
            where={"id": datasource_id},
            data=body.dict(),
        )
        return {"success": True, "data": data}
    except Exception as e:
        handle_exception(e)


@router.delete(
    "/datasources/{datasource_id}",
    name="delete",
    description="Delete a specific datasource",
)
async def delete(datasource_id: str, api_user_id=Depends(get_keycloak_user_id)): # modified
    """Endpoint for deleting a specific datasource"""
    try:
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": api_user_id}) # modified
        if not api_user:
            raise HTTPException(status_code=404, detail="API User not found") # modified
        
        if SEGMENT_WRITE_KEY:
            analytics.track(api_user.id, "Deleted Datasource")
        await prisma.agentdatasource.delete_many(where={"datasourceId": datasource_id})
        await prisma.datasource.delete(where={"id": datasource_id})
        return {"success": True, "data": None}
    except Exception as e:
        handle_exception(e)


@router.get(
    "/getSASToken/{blobName}",
    name="Get SAS Token",
    description="Generate and return the SAS token for a given blob",
)
async def get_sas_token(blobName: str, api_user_id=Depends(get_keycloak_user_id)):
    logger.info(f"get_sas_token called for blob: {blobName}")
    try:
        blob_service_client = BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net", credential=account_key)
        
        # Create a container for the user if it doesn't exist
        container_client = blob_service_client.get_container_client(container=api_user_id)
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass  # Container already exists, so pass

        # Create a SAS token that's valid for one day
        start_time = datetime.now(timezone.utc)
        expiry_time = start_time + timedelta(days=1)

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=str(api_user_id),
            blob_name=blobName,
            account_key=account_key,
            permission=BlobSasPermissions(read=True, write=True, delete=True),  # you can adjust permissions as needed
            expiry=expiry_time,
            start=start_time
        )

        logger.info(f"SAS token generated for blob: {blobName}")

        return {
            "success": True, 
            "sasToken": f"https://{account_name}.blob.core.windows.net/{str(api_user_id)}/{blobName}?{sas_token}"
        }

    except Exception as e:
        logger.error(f"Error generating SAS token for blob: {blobName}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
