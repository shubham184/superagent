import logging
from jose import JWTError, jwt
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import OAuth2PasswordBearer
import httpx
from typing import Dict

logger = logging.getLogger(__name__)

# OAuth2PasswordBearer is a class that provides a way to get the token from the request
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# URL of your Keycloak server
KEYCLOAK_URL = "http://localhost:8081/"
# The realm and client you created
REALM_NAME = "myrealm"
CLIENT_ID = "myclient"

# Fetch the public key from Keycloak
async def get_keycloak_public_key():
    url = f"{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/certs"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        return data["keys"][0]["x5c"][0]

# Decode and validate the JWT token
def decode_jwt(token: str, public_key: str) -> Dict:
    try:
        # Decode the token using the RS256 algorithm (asymmetric)
        return jwt.decode(token, public_key, algorithms=["RS256"], audience=CLIENT_ID)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token or expired token")

# Dependency to get the current user
async def get_current_api_user(token: str = Depends(oauth2_scheme)):
    public_key = await get_keycloak_public_key()
    decoded_token = decode_jwt(token, public_key)
    api_user_id = decoded_token.get("sub")  # subject claim contains the user ID
    # You can fetch additional user info from your database if needed
    return {"user_id": api_user_id}


def handle_exception(e):
    logger.error(e)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
    )
