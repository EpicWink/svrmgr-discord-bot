# Server manager Discord bot

<img src="logo.png" height="100">

AWS Lambda function which can manage EC2 instances, invoked from Discord integrations.

## Usage

### Setup

1. Create a Discord bot (aka app), get its bot token, add it to your server (aka guild)
   with bot:send-messages permission. Also add it to your channel if the channel is
   private.

2. Create message (see below).

3. Run Terraform (see [Terraform README](./terraform/README.md)). Enter the output
   function URL into the Discord app's integration URL.

3. Update servers (see below).

#### Create message

For initial setup, create the Discord message:

```shell
python scripts/create-message.py
```

Environment variables:

- `SVRMGR_DISCORD_API_URL` (optional): Discord API URL, defaults to
  https://discord.com/api.

- `SVRMGR_DISCORD_BOT_TOKEN`: Discord App bot token.

- `SVRMGR_DISCORD_CHANNEL_ID`: Discord channel ID (get by enabling dev-mode in Discord,
  then right-click on channel and select "Copy Channel ID").

#### Update servers

Currently only AWS EC2 instances are supported. Tag servers with `env:dev` (to allow
the function to manage the server) and `svrmgr-message-id:MESSAGE_ID` (to allow the
Discord message to manage the server).

`MESSAGE_ID` comes from the message-create script documented above, or by enabling
dev-mode in Discord and right-clicking on the message and selecting "Copy Message ID".

## Development

See [DEVELOPMENT.md](./DEVELOPMENT.md)
