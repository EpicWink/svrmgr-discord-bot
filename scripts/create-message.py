"""Create message in Discord to manage instances.

Reads a spec-nonconformant (assumes raw strings) .env file (in the
current directory) to load environment variables.

Environment variables:
- SVRMGR_DISCORD_API_URL (optional): Discord API base URL
- SVRMGR_DISCORD_CHANNEL_ID: Discord channel ID
- SVRMGR_DISCORD_BOT_TOKEN: Discord bot token
"""

import os
import pathlib
import sys

import requests

if sys.argv[1:]:
    print("Script takes no command-line arguments", file=sys.stderr)
    sys.exit(1)

# Read .env
env_path = pathlib.Path(".env")
if env_path:
    env_text = env_path.read_text()
    for line in env_text.splitlines():
        comment_start_index = line.find("#")
        if comment_start_index >= 0:
            line = line[:comment_start_index]

        line = line.strip()
        if not line:
            continue

        name, value = line.split("=", maxsplit=1)
        os.environ[name] = value

# Load environment variables
BASE_URL = os.environ.get("SVRMGR_DISCORD_API_URL", "https://discord.com/api/v10")
CHANNEL_ID = os.environ["SVRMGR_DISCORD_CHANNEL_ID"]
BOT_TOKEN = os.environ["SVRMGR_DISCORD_BOT_TOKEN"]
# CLIENT_ID = os.environ["SVRMGR_DISCORD_CLIENT_ID"]
# CLIENT_SECRET = os.environ["SVRMGR_DISCORD_CLIENT_SECRET"]

session = requests.Session()

# Make create-message request
request_data = {
    "content": "Servers",
    "components": [
        {
            "type": 1,
            "components": [
                {"type": 2, "label": "\u21bb", "style": 2, "custom_id": "refresh"},
            ],
        },
    ],
}

url = BASE_URL + f"/channels/{CHANNEL_ID}/messages"

print(f"Making POST request to: {url}", file=sys.stderr)
response = session.post(
    url, headers={"Authorization": f"Bot {BOT_TOKEN}"}, json=request_data
)

# Output response,
if not response.ok:
    print(response.text)
    response.raise_for_status()

response_data = response.json()
print("Message ID:", response_data["id"])
