"""Google API authentication utilities."""

import logging
import os
from typing import Any

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/presentations"]

TOKEN_PATH_ENV_VAR = "IMAGES2SLIDES_TOKEN_PATH"

logger = logging.getLogger(__name__)


def default_token_path() -> str:
    """Return the default path for the cached OAuth token file.

    Resolution order:
    1. The IMAGES2SLIDES_TOKEN_PATH environment variable, if set.
    2. The platform user config directory, so the token stops landing in the
       current working directory:
       - Windows: %APPDATA%/images2slides/token.json
       - Others: $XDG_CONFIG_HOME/images2slides/token.json (default ~/.config)

    Returns:
        Path to the OAuth token file.
    """
    env_path = os.environ.get(TOKEN_PATH_ENV_VAR)
    if env_path:
        return env_path

    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "images2slides", "token.json")


def get_slides_service_oauth(client_secret_path: str, token_path: str | None = None) -> Any:
    """Get authenticated Slides API service using OAuth.

    Args:
        client_secret_path: Path to OAuth client secret JSON file.
        token_path: Path to store/retrieve the cached OAuth token. Defaults to
            the user config directory (see default_token_path). The token file
            contains a refresh token in plaintext and is written with
            owner-only permissions (0600).

    Returns:
        Google Slides API service resource.
    """
    if token_path is None:
        token_path = default_token_path()

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
        creds = flow.run_local_server(port=0)
        parent_dir = os.path.dirname(token_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        try:
            os.chmod(token_path, 0o600)
        except OSError:
            logger.warning("Could not restrict permissions on token file: %s", token_path)

    return build("slides", "v1", credentials=creds)


def get_slides_service_sa(sa_json_path: str) -> Any:
    """Get authenticated Slides API service using service account.

    Args:
        sa_json_path: Path to service account JSON key file.

    Returns:
        Google Slides API service resource.
    """
    creds = service_account.Credentials.from_service_account_file(sa_json_path, scopes=SCOPES)
    return build("slides", "v1", credentials=creds)
