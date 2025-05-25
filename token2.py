import os
from msal import PublicClientApplication
from dotenv import load_dotenv

load_dotenv()
TENANT_ID    = os.getenv("TENANT_ID")
CLIENT_ID    = os.getenv("CLIENT_ID")
AUTHORITY    = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = [
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/OnlineMeetings.ReadWrite"
]


app = PublicClientApplication(
    client_id=CLIENT_ID,
    authority=AUTHORITY
)

flow = app.initiate_device_flow(scopes=SCOPES)
if "user_code" not in flow:
    raise ValueError(f"Failed to start device flow: {flow}")


print(flow["message"])  

result = app.acquire_token_by_device_flow(flow)  

if "access_token" in result:
    print("\n✅ Graph access token:\n")
    print(result["access_token"])
else:
    print("\n❌ Error obtaining token:\n")
    print(result)
