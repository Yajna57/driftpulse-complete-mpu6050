# Telegram alerts

DriftPulse can send a Telegram message whenever a new ELEVATED or ALERT event is raised. Each message contains the full alert details and a short list of what to do.

## What you get

An alert message contains:

- Severity (ELEVATED or ALERT), user id, risk score (0-100) and the detected activity.
- The summary text.
- The current heart rate, RMSSD, SDNN and temperature, each with its z-score against the user's personal baseline.
- The reasons the alert fired (the observations list).
- A numbered "What to do" list that depends on severity.
- A reminder that this is an educational prototype and not a medical diagnosis.

## How messages are routed

Two kinds of chat can be configured, and both are optional:

| Chat | Receives | Configured |
| --- | --- | --- |
| **User chat** | Alerts for one specific user only | Per user, in Settings |
| **General chat** | Alerts for every user | Once, in Settings |

When an alert fires for a user, it is sent to that user's chat and to the general chat. If both are set to the same chat id, the message is sent once. A chat that is switched off in Settings is skipped. A single bot token is shared by both.

To avoid flooding, the backend creates at most one alert per user and severity every 5 minutes, and a Telegram message is sent only when a new alert is created.

## One-time setup

### 1. Create the bot

1. In Telegram, open **@BotFather** and send `/newbot`.
2. Choose a display name and a username ending in `bot`.
3. BotFather replies with a token that looks like `123456789:ABCdef...`. Keep it private.

### 2. Start the bot chat

Open your new bot in Telegram and press **Start**. Telegram does not allow a bot to message someone who has never started it. Every person who should receive alerts must do this once.

### 3. Find the chat id

1. Send any message to the bot (for example `hello`).
2. Open this address in a browser, replacing `<TOKEN>` with your token:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find `"chat":{"id":123456789,...}`. That number is the chat id.

For a group, add the bot to the group first, send a message in the group, then read `getUpdates` the same way. Group ids are negative, for example `-1001234567890`. A public channel can also be entered as `@channelname`, as long as the bot is an admin of it.

If `getUpdates` returns an empty result, send another message to the bot and reload.

### 4. Configure DriftPulse

1. Start the backend and the frontend as usual. The backend creates the `telegram_configs` table automatically on startup, so no migration is needed.
2. Open the dashboard and click **Settings** in the header.
3. Under **General (all users)**, paste the bot token and, if you want one shared chat, the general chat id. Click **Save**, then **Send test**.
4. To give one person their own alerts, select that user in the **User** dropdown, enter their personal chat id under the user section, click **Save**, then **Send test**.

The test message confirms the token and chat id work. It does not create an alert.

## Settings reference

| Field | Meaning |
| --- | --- |
| Bot token | Token from BotFather. Once saved it is shown only in masked form. Leave the field blank to keep the saved token. |
| General chat id | Chat that receives alerts for all users. |
| Send every user's alerts here | Switch for the general chat. |
| Personal chat id | Chat that receives alerts for the selected user only. |
| Send this user's alerts here | Switch for that user's chat. |
| Remove token | Deletes the saved token. Alerts stop being sent. |

Accepted chat id formats are a number such as `987654321` or `-1001234567890`, or `@channelname`. The bot token must match the BotFather format. Invalid values are rejected with a message in the panel.

## Optional: token from `.env`

If no token is saved in Settings, the backend falls back to an environment variable. Add this to `python/.env`:

```
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
```

A token saved in Settings takes priority over the environment variable. Chat ids are always configured in Settings.

## Testing with a real alert

The quickest way to trigger an alert is one of the simulated cases in `docs/SIMULATION.md` that drives the status to ELEVATED or ALERT, after the baseline has been calibrated. Watch the chats you configured. Remember the 5-minute limit when running several tests in a row.

## API

The Settings panel uses these endpoints. All are under `/api/v1/settings/telegram`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `?user_id=<id>` | Read current settings. The token is returned masked. |
| PUT | `/general` | Save token, general chat id and switch. `bot_token` omitted or `null` keeps the saved token, and an empty string removes it. |
| PUT | `/users/{user_id}` | Save one user's chat id and switch. |
| POST | `/test` | Send a test message. Body `{"user_id": "USER001"}` for a user chat, or `{"user_id": null}` for the general chat. |

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| "Telegram rejected the message: Unauthorized" | The token is wrong or was revoked. Create a new one with BotFather's `/token` and save it again. |
| "Bad Request: chat not found" | The chat id is wrong, or the person never pressed Start. For a group, make sure the bot was added. |
| "Forbidden: bot was blocked by the user" | The user blocked the bot. Unblock it in Telegram. |
| "Network error" | The backend cannot reach `api.telegram.org`. Check internet access, proxy or firewall. |
| Test works but real alerts do not arrive | The chat is switched off, the status never reached ELEVATED or ALERT, or an alert for that user and severity was already sent in the last 5 minutes. |
| Messages sent twice | The user chat and the general chat are different chats that you both read. This is expected. |

Failed automatic sends do not interrupt reading ingestion. They are logged as warnings by the backend (`telegram send to ... failed`).

## Security notes

- The API has no login. Anyone who can reach the backend can read or change the Telegram settings and send test messages. Do not expose the backend to the internet without adding authentication.
- The bot token is stored in plain text in the database table `telegram_configs`, and the API never returns it unmasked. Treat database backups as sensitive.
- If a token leaks, revoke it in BotFather with `/revoke` and save the new one.
- Alert messages contain health-related readings. Send them only to chats whose members should see that data, and prefer private chats over large groups.
- The "What to do" advice is generic and is not medical advice. Have a qualified person review the wording before using the system outside a classroom demo. The text is in `ACTIONS` in `python/backend/app/services/telegram.py`.

## Where the code lives

- `python/backend/app/services/telegram.py`: message text, recipient lookup, sending.
- `python/backend/app/routers/telegram.py`: the Settings API.
- `python/backend/app/models.py`: the `TelegramConfig` table.
- `python/backend/app/services/analysis.py`: queues a message when a new alert row is created.
- `python/backend/app/routers/readings.py`: sends queued messages after the database commit.
- `frontend/src/components/SettingsPanel.tsx`: the Settings panel.
