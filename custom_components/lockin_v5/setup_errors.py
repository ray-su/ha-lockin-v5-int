"""Allowlisted setup-error descriptions; never stringify an exception or payload."""
import json
import ssl

import aiohttp

from .miot.miot_error import MIoTError, MIoTHttpError, MIoTOauthError


def safe_error_summary(error: Exception) -> str:
    """Return only fixed categories and validated transport/API numeric codes."""
    if isinstance(error, TimeoutError):
        category = "Request timed out"
    elif isinstance(error, (aiohttp.ClientSSLError, ssl.SSLError)):
        category = "TLS connection error"
    elif isinstance(error, aiohttp.ClientConnectorDNSError):
        category = "DNS lookup failed"
    elif isinstance(error, aiohttp.ClientConnectionError):
        category = "Connection failed"
    elif isinstance(error, json.JSONDecodeError):
        category = "Invalid JSON response"
    elif isinstance(error, MIoTOauthError):
        category = "OAuth response error"
    elif isinstance(error, MIoTHttpError):
        category = "Cloud API error"
    elif isinstance(error, aiohttp.ClientError):
        category = "HTTP client error"
    elif type(error) in (KeyError, TypeError, ValueError, AttributeError):
        category = f"Internal or response error ({type(error).__name__})"
    else:
        category = "Unexpected internal error"
    details = [category]
    if isinstance(error, MIoTError):
        # Revalidate, including against attributes changed after construction.
        status = error.http_status
        code = error.cloud_code
        if type(status) is int and 100 <= status <= 599:
            details.append(f"HTTP {status}")
        if type(code) is int and -2147483648 <= code <= 2147483647:
            details.append(f"API code {code}")
    return "; ".join(details)
