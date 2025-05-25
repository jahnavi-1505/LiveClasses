from msal import ConfidentialClientApplication
import os
from dotenv import load_dotenv
TENANT_ID    = os.getenv("TENANT_ID")
CLIENT_ID    = os.getenv("CLIENT_ID")
app = ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=os.getenv("BACKEND_APP_SECRET"),
    authority="https://login.microsoftonline.com/f06a8b29-0dfb-454f-aabd-18109c46e51d"
)

result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
if "access_token" in result:
    print("\n✅ Graph access token:\n")
    print(result["access_token"])