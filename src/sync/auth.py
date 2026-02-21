"""
Run once to obtain a Gmail OAuth refresh token.
Uses InstalledAppFlow which handles the unverified app warning for Desktop apps.

Requires credentials.json downloaded from Google Cloud Console:
  Clients → your Desktop app client → Download JSON → save as credentials.json

Usage: uv run sync-auth
"""

from google_auth_oauthlib.flow import InstalledAppFlow

import resolve

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main() -> None:
    creds_file = resolve.credentials_json()
    if not creds_file.exists():
        raise SystemExit(
            "credentials.json not found.\n"
            "Download it from Google Cloud Console → Clients →"
            " your Desktop app → Download JSON\n"
            "and save it as credentials.json in the project root."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
    flow.redirect_uri = "http://localhost:3000/"
    print(f"Using redirect URI: {flow.redirect_uri}")
    creds = flow.run_local_server(
        port=3000,
        authorization_prompt_message=(
            "Please visit this URL to authorize this application:\n{url}\n"
        ),
    )

    if not creds.refresh_token:
        raise SystemExit(
            "\nNo refresh token returned. Revoke previous access and try again:\n"
            "https://myaccount.google.com/permissions"
        )

    print("\nAdd this to your .env:\n")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
