from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secrets.json", SCOPES
)

creds = flow.run_local_server(
    port=0,
    access_type="offline",
    prompt="consent"
)

if not creds.refresh_token:
    raise RuntimeError("No refresh token received")

with open("token.json", "w") as f:
    f.write(creds.to_json())

print("✅ OAuth token created successfully")