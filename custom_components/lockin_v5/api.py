"""Read-only adapter around the pinned upstream cloud transport."""
from .miot.const import OAUTH2_CLIENT_ID, OAUTH_REDIRECT_URL
from .miot.miot_cloud import MIoTHttpClient, MIoTOauthClient
from .miot.miot_error import MIoTError, MIoTErrorCode


def auth_failure(error: Exception) -> bool:
    return isinstance(error, MIoTError) and error.code in (
        MIoTErrorCode.CODE_OAUTH_UNAUTHORIZED, MIoTErrorCode.CODE_HTTP_INVALID_ACCESS_TOKEN
    )


class ReadOnlyClient(MIoTHttpClient):
    async def set_prop_async(self, *args, **kwargs):
        raise PermissionError("This integration has no device-control capability")

    async def action_async(self, *args, **kwargs):
        raise PermissionError("This integration has no device-control capability")


def oauth_client(region: str, uuid: str, redirect: str) -> MIoTOauthClient:
    return MIoTOauthClient(client_id=OAUTH2_CLIENT_ID, redirect_url=redirect, cloud_server=region, uuid=uuid)


def http_client(region: str, uuid: str, token: str) -> ReadOnlyClient:
    return ReadOnlyClient(cloud_server=region, client_id=OAUTH2_CLIENT_ID, access_token=token, uuid=uuid)


def redirect_url(webhook_id: str) -> str:
    # Preserve upstream's registered OAuth origin. No DNS/proxy changes here.
    return f"{OAUTH_REDIRECT_URL}/api/webhook/{webhook_id}"
