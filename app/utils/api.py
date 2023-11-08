import logging
from jose import JWTError, jwt
from fastapi import HTTPException, Security, Depends, status # added for the line 45
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from typing import Dict
import base64
import json
from app.utils.prisma import prisma

logger = logging.getLogger(__name__)
security = HTTPBearer()

# URL of your Keycloak server
KEYCLOAK_URL = "http://localhost:8081/"
# The realm and client you created
REALM_NAME = "myrealm"
CLIENT_ID = "myclient"

async def get_current_api_user(authorization: HTTPAuthorizationCredentials = Depends(security)):
    token = authorization.credentials
    try:
        public_key = await get_keycloak_public_key()
        decoded_token = decode_jwt(token, public_key)
        keycloak_user_id = decoded_token.get("sub")
        api_user = await prisma.apiuser.find_unique(where={"keycloakUserId": keycloak_user_id})
        return api_user  # Return the user or None if not found
    except JWTError as e:
        logger.error(f"JWT error occurred: {e}")
        return None  # Return None instead of raising an error

# Make sure to cache the public key appropriately here

# Updated decode_jwt function
def decode_jwt(token: str, public_key: str) -> Dict:
    try:
        return jwt.decode(token, public_key, algorithms=["RS256"], audience="account")
    except JWTError as e:
        logger.error(f"JWT error occurred: {e}")
        raise HTTPException(status_code=401, detail="Invalid token or expired token")

def handle_exception(e):
    logger.error(e)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
    )

async def get_keycloak_public_key():
    url = f"{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/certs"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            # Convert the x5c value to PEM format
            cert_b64 = data["keys"][0]["x5c"][0]
            pem_cert = convert_cert_to_pem(cert_b64)
            return pem_cert
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise HTTPException(status_code=500, detail="Could not fetch public key from Keycloak")
        except KeyError:
            logger.error("Unexpected response format from Keycloak when fetching public key")
            raise HTTPException(status_code=500, detail="Invalid response from Keycloak")

def convert_cert_to_pem(cert_b64):
    pem_cert = "-----BEGIN CERTIFICATE-----\n"
    wrapped_cert = "\n".join(cert_b64[i:i+64] for i in range(0, len(cert_b64), 64))
    pem_cert += wrapped_cert + "\n-----END CERTIFICATE-----\n"
    return pem_cert


async def get_keycloak_user_id(authorization: HTTPAuthorizationCredentials = Depends(security)):
    token = authorization.credentials
    try:
        public_key = await get_keycloak_public_key()
        decoded_token = decode_jwt(token, public_key)
        keycloak_user_id = decoded_token.get("sub")
        return keycloak_user_id
    except JWTError as e:
        logger.error(f"JWT error occurred: {e}")
        raise HTTPException(status_code=401, detail="Invalid token or expired token")

