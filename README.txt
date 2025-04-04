- Overview

Telegram Cloner Bot is a Python-based tool that allows you to clone messages from one Telegram source (channel, group, or chat) to another destination. It supports a wide range of filtering options, content transformations, and media handling capabilities.

- Features

- Complete Message Cloning: Text, media, polls, contacts, and more
- Media Support: Photos, videos, documents, voice messages, music, GIFs, stickers
- Reply Structure Preservation: Maintains conversation threads
- Album Support: Keeps media groups together
- Forward Handling: Clone forwarded messages with attribution or anonymously
- Extensive Filtering Options:
  - Date range
  - Message length
  - Content keywords
  - User filtering
  - Message IDs range
- Content Transformation:
  - Text replacements
  - URL removal
  - Source attribution
- Detailed Logging and Statistics

- Requirements

- Python 3.7+
- Telegram API credentials (API ID and Hash)
- A Telegram account

- Installation

 Install the required Python packages:
   pip install telethon python-dotenv


- Getting Telegram API Credentials

1. Visit https://my.telegram.org/apps
2. Log in with your phone number
3. Create a new application
4. Note your API ID and API Hash

- Configuration

Edit the `.env` file with your settings:

-# Required Settings


# Telegram API credentials
API_ID=your_api_id_here
API_HASH=your_api_hash_here
SESSION_NAME=cloner_session

# Source and destination
SOURCE_ENTITY=@source_channel_username
DESTINATION_ENTITY=@destination_channel_username


-# Optional Settings


# General settings
MAX_MESSAGES=0               # 0 means no limit
DELAY_BETWEEN_MESSAGES=1.5   # Delay in seconds between sending messages
START_FROM_MESSAGE_ID=0      # 0 means start from newest/oldest based on REVERSE_ORDER
END_AT_MESSAGE_ID=0          # 0 means no end limit

# Media filters (set to True/False)
CLONE_PHOTOS=True
CLONE_VIDEOS=True
CLONE_FILES=True
CLONE_VOICES=True
CLONE_MUSIC=True
CLONE_GIFS=True
CLONE_STICKERS=True
CLONE_POLLS=True
CLONE_CONTACTS=True
CLONE_ALBUMS=True
CLONE_FORWARDS=True

# Content filters
MIN_MESSAGE_LENGTH=0         # 0 means no minimum
MAX_MESSAGE_LENGTH=0         # 0 means no maximum
MESSAGE_CONTAINS=            # Comma-separated words that must be in messages
MESSAGE_NOT_CONTAINS=        # Comma-separated words to filter out
BLACKLISTED_USERS=           # Comma-separated usernames to filter out

# Time filters (YYYY-MM-DD format)
START_DATE=                  # Empty means no start date filter
END_DATE=                    # Empty means no end date filter

# Content transformation
REPLACE_TEXT=False
TEXT_REPLACEMENTS=original:replacement,word:new_word  # Format: "original1:replacement1,original2:replacement2"
ADD_SOURCE_LINK=False        # Adds a link to original message
REMOVE_URLS=False            # Removes URLs from messages
ANONYMIZE_FORWARDS=False     # Clone forwarded messages as regular messages


- Usage

1. Ensure you've set up the `.env` file with your credentials and settings
2. Run the script:
   
   python main.py
   
3. On first run, you'll be prompted to log in with your Telegram account
4. The script will start cloning messages according to your settings

- Detailed Configuration Options

-# Source and Destination

The `SOURCE_ENTITY` and `DESTINATION_ENTITY` can be specified in several formats:
- Username: `@username`
- Chat/Channel ID: `-1001234567890`
- Private chat phone number: `+1234567890`
- Invite link: `https://t.me/joinchat/XXXXXXXX`

-# Message Selection

- `MAX_MESSAGES`: Maximum number of messages to clone (0 = unlimited)
- `START_FROM_MESSAGE_ID`: Start cloning from this message ID (0 = start from newest/oldest)
- `END_AT_MESSAGE_ID`: Stop cloning at this message ID (0 = no limit)
- `REVERSE_ORDER`: Always set to True in the code to clone from oldest to newest

-# Message Timing

- `DELAY_BETWEEN_MESSAGES`: Seconds to wait between sending messages (recommended: at least 1 second to avoid rate limits)

-# Date Range Filtering

Format: YYYY-MM-DD
- `START_DATE`: Only clone messages sent on or after this date
- `END_DATE`: Only clone messages sent on or before this date

-# Content Filtering

- `MIN_MESSAGE_LENGTH` and `MAX_MESSAGE_LENGTH`: Filter messages by character count
- `MESSAGE_CONTAINS`: Only clone messages containing these comma-separated words/phrases
- `MESSAGE_NOT_CONTAINS`: Skip messages containing these comma-separated words/phrases
- `BLACKLISTED_USERS`: Skip messages from these comma-separated usernames

-# Content Transformation

- `REPLACE_TEXT`: Enable text replacements
- `TEXT_REPLACEMENTS`: Format: "original1:replacement1,original2:replacement2"
- `ADD_SOURCE_LINK`: Add a footer with link to original message
- `REMOVE_URLS`: Strip all URLs from messages
- `ANONYMIZE_FORWARDS`: Clone forwarded messages as regular messages

- Limitations and Notes

- Rate Limiting: Telegram has rate limits. Use a reasonable `DELAY_BETWEEN_MESSAGES` value (1-2 seconds recommended)
- Permissions: You need to be a member of both source and destination chats
- Media Downloads: All media is temporarily downloaded to a "downloads" folder
- Large Media: Very large files might fail to clone due to Telegram's limitations
- Session File: A session file will be created in your directory - keep it secure as it contains your authentication

- Troubleshooting

-# Common Issues

1. FloodWaitError: You're sending messages too quickly. Increase `DELAY_BETWEEN_MESSAGES` value.
2. ChannelPrivateError: You don't have access to the source or destination channel.
3. ChatAdminRequiredError: You need admin rights in the destination channel.
4. Media Download Fails: Check your internet connection and disk space.

-# Logging

The script creates detailed logs in the `telegram_cloner.log` file which can help diagnose issues.

- Advanced Usage

-# Selective Media Cloning

You can set specific media types to False to skip cloning them:

CLONE_PHOTOS=False
CLONE_VIDEOS=True
# etc.


-# Text Replacements

You can set up automatic text replacements using the `TEXT_REPLACEMENTS` option. This is useful for:
- Changing channel names
- Updating outdated information
- Replacing specific terms
- Censoring information

Example:

REPLACE_TEXT=True
TEXT_REPLACEMENTS=OldName:NewName,http://oldlink.com:http://newlink.com,badword:*
