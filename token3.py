import os
from dotenv import load_dotenv
from msal import PublicClientApplication, SerializableTokenCache
import atexit
import json

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CACHE_FILE = "token_cache.bin"
TOKEN_OUTPUT_FILE = ".access_token"

cache = SerializableTokenCache()
if os.path.exists(CACHE_FILE):
    cache.deserialize(open(CACHE_FILE, "r").read())

def save_cache():
    if cache.has_state_changed:
        with open(CACHE_FILE, "w") as f:
            f.write(cache.serialize())
atexit.register(save_cache)

app = PublicClientApplication(
    client_id=CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    token_cache=cache
)

SCOPES = ["User.Read", "OnlineMeetings.ReadWrite"]

accounts = app.get_accounts()
result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None

if not result:
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError("Failed to initiate device flow")
    print("📱 Authenticate with this code:\n", flow["message"])
    result = app.acquire_token_by_device_flow(flow)

if "access_token" in result:
    access_token = result["access_token"].replace("\n", "").replace(" ", "").strip()
    with open(TOKEN_OUTPUT_FILE, "w") as f:
        f.write(access_token)
    print("\n✅ Access token stored in .access_token")
else:
    print("\n❌ ERROR:")
    print(json.dumps(result, indent=2))
