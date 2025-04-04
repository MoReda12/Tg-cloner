import os
import re
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Union, Optional, Set

from telethon import TelegramClient
from telethon.tl.types import (
    Message, MessageService, MessageMediaPhoto, MessageMediaDocument,
    MessageMediaWebPage, MessageMediaPoll, MessageMediaContact,
    User, Channel, InputChannel, Chat, PeerChannel, PeerChat, PeerUser,
    MessageEntityTextUrl, MessageEntityMention, MessageEntityMentionName,
    Document, DocumentAttributeVideo, DocumentAttributeAudio,
    DocumentAttributeSticker, DocumentAttributeAnimated
)
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.errors import (
    ChannelPrivateError, ChatAdminRequiredError, UserNotParticipantError,
    FloodWaitError, ChatWriteForbiddenError, SlowModeWaitError
)
from telethon.utils import get_peer_id, resolve_id
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='telegram_cloner.log'
)
logger = logging.getLogger(__name__)
# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

# Get environment variables
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SESSION_NAME = os.getenv('SESSION_NAME', 'cloner_session')
SOURCE_ENTITY = os.getenv('SOURCE_ENTITY')
DESTINATION_ENTITY = os.getenv('DESTINATION_ENTITY')

# Additional configuration from environment
MAX_MESSAGES = int(os.getenv('MAX_MESSAGES', '0'))  # 0 means no limit
DELAY_BETWEEN_MESSAGES = float(os.getenv('DELAY_BETWEEN_MESSAGES', '2.0'))  # Increased default delay
START_FROM_MESSAGE_ID = int(os.getenv('START_FROM_MESSAGE_ID', '0'))
END_AT_MESSAGE_ID = int(os.getenv('END_AT_MESSAGE_ID', '0'))
REVERSE_ORDER = True  # Always clone from oldest to newest
INCLUDE_REPLIES = True  # Always include replies

# Media filters - all set to True by default
CLONE_PHOTOS = True
CLONE_VIDEOS = True
CLONE_FILES = True
CLONE_VOICES = True
CLONE_MUSIC = True
CLONE_GIFS = True
CLONE_STICKERS = True
CLONE_POLLS = True
CLONE_CONTACTS = True
CLONE_ALBUMS = True
CLONE_FORWARDS = True

# Content filters - disabled by default for complete cloning
MIN_MESSAGE_LENGTH = 0
MAX_MESSAGE_LENGTH = 0
MESSAGE_CONTAINS = ""
MESSAGE_NOT_CONTAINS = ""
BLACKLISTED_USERS = ""

# Time filters
START_DATE = os.getenv('START_DATE', '')
END_DATE = os.getenv('END_DATE', '')

# Transform configuration
REPLACE_TEXT = os.getenv('REPLACE_TEXT', 'False').lower() == 'true'
TEXT_REPLACEMENTS = os.getenv('TEXT_REPLACEMENTS', '')
ADD_SOURCE_LINK = os.getenv('ADD_SOURCE_LINK', 'False').lower() == 'true'
REMOVE_URLS = os.getenv('REMOVE_URLS', 'False').lower() == 'true'
ANONYMIZE_FORWARDS = os.getenv('ANONYMIZE_FORWARDS', 'False').lower() == 'true'

# Parse replacements
text_replacements_dict = {}
if TEXT_REPLACEMENTS:
    for pair in TEXT_REPLACEMENTS.split(','):
        if ':' in pair:
            original, replacement = pair.split(':', 1)
            text_replacements_dict[original.strip()] = replacement.strip()

# Parse content filters
message_contains = [word.strip() for word in MESSAGE_CONTAINS.split(',') if word.strip()]
message_not_contains = [word.strip() for word in MESSAGE_NOT_CONTAINS.split(',') if word.strip()]
blacklisted_users = [user.strip() for user in BLACKLISTED_USERS.split(',') if user.strip()]

# Parse dates
start_date = None
if START_DATE:
    try:
        start_date = datetime.strptime(START_DATE, '%Y-%m-%d')
    except ValueError:
        logger.error(f"Invalid START_DATE format: {START_DATE}. Using YYYY-MM-DD.")

end_date = None
if END_DATE:
    try:
        end_date = datetime.strptime(END_DATE, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        logger.error(f"Invalid END_DATE format: {END_DATE}. Using YYYY-MM-DD.")

class TelegramCloner:
    def __init__(self):
        self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        self.source_entity = None
        self.destination_entity = None
        self.message_map = {}  # Maps source message IDs to destination message IDs
        self.processed_messages_ids = set()
        self.seen_album_ids = set()
        self.pending_replies = {}  # Messages waiting for their reply-to target to be processed
        self.stats = {
            'total': 0,
            'cloned': 0,
            'skipped': 0,
            'failed': 0,
            'photos': 0,
            'videos': 0,
            'files': 0,
            'voices': 0,
            'music': 0,
            'gifs': 0,
            'stickers': 0,
            'polls': 0,
            'contacts': 0,
            'albums': 0,
            'forwards': 0,
            'text_only': 0
        }

    async def connect(self):
        """Connect to Telegram and resolve entities"""
        await self.client.start()
        logger.info("Connected to Telegram")
        
        # Get source entity
        try:
            self.source_entity = await self.client.get_entity(SOURCE_ENTITY)
            logger.info(f"Source entity found: {getattr(self.source_entity, 'title', getattr(self.source_entity, 'first_name', SOURCE_ENTITY))}")
        except Exception as e:
            logger.error(f"Error getting source entity: {e}")
            raise
        
        # Get destination entity
        try:
            self.destination_entity = await self.client.get_entity(DESTINATION_ENTITY)
            logger.info(f"Destination entity found: {getattr(self.destination_entity, 'title', getattr(self.destination_entity, 'first_name', DESTINATION_ENTITY))}")
        except Exception as e:
            logger.error(f"Error getting destination entity: {e}")
            raise

    async def get_messages(self):
        """Get messages from source entity with applied filters"""
        logger.info("Starting to fetch messages from source")
        
        # Set up parameters for iterating through messages
        params = {
            'reverse': True,  # Always get oldest first
            'limit': None if MAX_MESSAGES == 0 else MAX_MESSAGES
        }
        
        if START_FROM_MESSAGE_ID > 0:
            params['min_id'] = START_FROM_MESSAGE_ID - 1
        
        if END_AT_MESSAGE_ID > 0:
            params['max_id'] = END_AT_MESSAGE_ID
        
        # Get messages
        messages = []
        try:
            async for message in self.client.iter_messages(self.source_entity, **params):
                if message and not isinstance(message, MessageService):
                    messages.append(message)
                    self.stats['total'] += 1
                    if MAX_MESSAGES > 0 and len(messages) >= MAX_MESSAGES:
                        break
                    
                    # Log every 100 messages fetched
                    if len(messages) % 100 == 0:
                        logger.info(f"Fetched {len(messages)} messages so far...")
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            raise
        
        logger.info(f"Fetched {len(messages)} messages from source")
        return messages

    async def process_message(self, message):
        """Process a single message and clone it to destination"""
        try:
            # Skip already processed messages
            if message.id in self.processed_messages_ids:
                return None
            
            self.processed_messages_ids.add(message.id)
            
            # Log message details for debugging
            logger.info(f"Processing message {message.id}: {getattr(message, 'text', '')[:30]}...")
            
            # Handle albums (group all album messages together)
            if message.grouped_id and message.grouped_id in self.seen_album_ids:
                logger.info(f"Skipping already processed album message {message.id}")
                self.stats['skipped'] += 1
                return None
                
            if message.grouped_id:
                self.seen_album_ids.add(message.grouped_id)
                
            # Transform message text if needed
            text = message.text or ""
            file = None
            
            # Apply text replacements
            if REPLACE_TEXT and text:
                for original, replacement in text_replacements_dict.items():
                    text = text.replace(original, replacement)
            
            # Remove URLs if requested
            if REMOVE_URLS and text:
                url_pattern = r'(https?://\S+)'
                text = re.sub(url_pattern, '', text)
                tme_pattern = r'(t\.me/\S+)'
                text = re.sub(tme_pattern, '', text)
                text = re.sub(r' +', ' ', text).strip()
            
            # Add source link if requested
            if ADD_SOURCE_LINK and isinstance(self.source_entity, (Channel, Chat)):
                source_title = getattr(self.source_entity, 'title', 'Source')
                if isinstance(self.source_entity, Channel) and self.source_entity.username:
                    source_link = f"https://t.me/{self.source_entity.username}/{message.id}"
                    footer = f"\n\n[Original post]({source_link}) from [{source_title}](https://t.me/{self.source_entity.username})"
                    text += footer
            
            # Handle media
            if message.media:
                logger.info(f"Message {message.id} contains media.")
                try:
                    # Download media
                    if isinstance(message.media, MessageMediaPhoto):
                        logger.info(f"Downloading photo from message {message.id}")
                        file = await message.download_media(file="downloads/")
                        self.stats['photos'] += 1
                    elif isinstance(message.media, MessageMediaDocument):
                        logger.info(f"Downloading document from message {message.id}")
                        file = await message.download_media(file="downloads/")
                        
                        # Classify media type
                        document = message.media.document
                        if document.attributes:
                            for attr in document.attributes:
                                if isinstance(attr, DocumentAttributeVideo):
                                    self.stats['videos'] += 1
                                    break
                                elif isinstance(attr, DocumentAttributeAudio):
                                    if attr.voice:
                                        self.stats['voices'] += 1
                                    else:
                                        self.stats['music'] += 1
                                    break
                                elif isinstance(attr, DocumentAttributeSticker):
                                    self.stats['stickers'] += 1
                                    break
                                elif isinstance(attr, DocumentAttributeAnimated):
                                    self.stats['gifs'] += 1
                                    break
                            else:
                                self.stats['files'] += 1
                    
                    elif isinstance(message.media, MessageMediaPoll):
                        logger.info(f"Processing poll from message {message.id}")
                        self.stats['polls'] += 1
                        
                        # Clone the poll
                        try:
                            new_message = await self.client.send_message(
                                self.destination_entity,
                                text if text else message.media.poll.question,
                                poll=message.media.poll
                            )
                            self.message_map[message.id] = new_message.id
                            self.stats['cloned'] += 1
                            logger.info(f"Cloned poll message {message.id} -> {new_message.id}")
                            return new_message
                        except Exception as e:
                            logger.error(f"Error cloning poll: {e}")
                            # Fallback to text-only if poll fails
                            text = f"{text}\n\nPoll: {message.media.poll.question}"
                            for option in message.media.poll.answers:
                                text += f"\n- {option.text}"
                    
                    elif isinstance(message.media, MessageMediaContact):
                        logger.info(f"Processing contact from message {message.id}")
                        self.stats['contacts'] += 1
                        
                        # Clone contact
                        try:
                            contact = message.media.contact
                            new_message = await self.client.send_message(
                                self.destination_entity,
                                text,
                                contact=contact
                            )
                            self.message_map[message.id] = new_message.id
                            self.stats['cloned'] += 1
                            logger.info(f"Cloned contact message {message.id} -> {new_message.id}")
                            return new_message
                        except Exception as e:
                            logger.error(f"Error cloning contact: {e}")
                            # Fallback to text
                            contact = message.media.contact
                            text = f"{text}\n\nContact: {contact.first_name} {contact.last_name or ''}\nPhone: {contact.phone_number}"
                except Exception as e:
                    logger.error(f"Error handling media in message {message.id}: {e}")
                    # Continue with text-only if media fails
            
            # Handle replies
            reply_to = None
            if message.reply_to:
                reply_msg_id = message.reply_to.reply_to_msg_id
                if reply_msg_id in self.message_map:
                    reply_to = self.message_map[reply_msg_id]
                    logger.info(f"Message {message.id} is a reply to {reply_msg_id} -> {reply_to}")
            
            # Handle forwarded messages
            if message.fwd_from and not ANONYMIZE_FORWARDS:
                logger.info(f"Message {message.id} is a forward")
                self.stats['forwards'] += 1
                
                # Clone as a forward
                try:
                    if hasattr(message.fwd_from, 'from_id') and message.fwd_from.from_id:
                        # Try to get the original sender entity
                        try:
                            from_entity = await self.client.get_entity(message.fwd_from.from_id)
                            new_message = await self.client.send_message(
                                self.destination_entity,
                                text,
                                file=file,
                                reply_to=reply_to,
                                forward=(from_entity, message.fwd_from.channel_post if hasattr(message.fwd_from, 'channel_post') else None)
                            )
                        except Exception as e:
                            logger.error(f"Error forwarding message with original entity {message.id}: {e}")
                            # Fallback: send as regular message
                            new_message = await self.client.send_message(
                                self.destination_entity,
                                f"{text}\n\n[Forwarded message]",
                                file=file,
                                reply_to=reply_to
                            )
                    else:
                        # Can't determine forward source, send as regular message
                        new_message = await self.client.send_message(
                            self.destination_entity,
                            f"{text}\n\n[Forwarded message]",
                            file=file,
                            reply_to=reply_to
                        )
                except Exception as e:
                    logger.error(f"Error handling forward for message {message.id}: {e}")
                    # Another fallback
                    new_message = await self.client.send_message(
                        self.destination_entity,
                        f"{text}\n\n[Forwarded message]",
                        file=file,
                        reply_to=reply_to
                    )
            else:
                # Regular message
                logger.info(f"Sending regular message {message.id} with text: {text[:30]}...")
                
                try:
                    new_message = await self.client.send_message(
                        self.destination_entity,
                        text,
                        file=file,
                        reply_to=reply_to
                    )
                    
                    if not file and not message.fwd_from:
                        self.stats['text_only'] += 1
                except Exception as e:
                    logger.error(f"Error sending message {message.id}: {e}")
                    # Try with just text if file sending fails
                    if file:
                        try:
                            new_message = await self.client.send_message(
                                self.destination_entity,
                                f"{text}\n\n[Media could not be sent]",
                                reply_to=reply_to
                            )
                        except Exception as e2:
                            logger.error(f"Error sending fallback text message {message.id}: {e2}")
                            self.stats['failed'] += 1
                            return None
                
            # Store message mapping for replies
            self.message_map[message.id] = new_message.id
            self.stats['cloned'] += 1
            
            # Clean up downloaded file
            if file and os.path.exists(file):
                os.remove(file)
                
            logger.info(f"Successfully cloned message {message.id} -> {new_message.id}")
            return new_message
            
        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: Waiting for {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return await self.process_message(message)
            
        except (ChatWriteForbiddenError, ChatAdminRequiredError) as e:
            logger.error(f"Permission error: {e}")
            self.stats['failed'] += 1
            return None
            
        except SlowModeWaitError as e:
            logger.warning(f"SlowModeWaitError: Waiting for {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return await self.process_message(message)
            
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")
            self.stats['failed'] += 1
            return None

    async def start_cloning(self):
        """Start the cloning process"""
        try:
            # Make sure the downloads directory exists
            os.makedirs("downloads", exist_ok=True)
            
            await self.connect()
            
            # Get messages from source
            messages = await self.get_messages()
            
            if not messages:
                logger.error("No messages found to clone!")
                return self.stats
            
            # Process messages in chronological order (oldest first)
            logger.info(f"Starting to clone {len(messages)} messages")
            
            for i, message in enumerate(messages):
                try:
                    if i > 0 and DELAY_BETWEEN_MESSAGES > 0:
                        await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
                    
                    await self.process_message(message)
                    
                    # Print progress
                    if (i + 1) % 10 == 0 or i == len(messages) - 1:
                        progress = (i + 1) / len(messages) * 100
                        logger.info(f"Progress: {progress:.1f}% ({i + 1}/{len(messages)})")
                        print(f"Progress: {progress:.1f}% ({i + 1}/{len(messages)})")
                        
                except Exception as e:
                    logger.error(f"Error in message {message.id}: {e}")
                    continue
            
            # Log final stats
            logger.info("Cloning completed!")
            logger.info(f"Stats: {self.stats}")
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Error in cloning process: {e}")
            raise
        finally:
            # Clean up any leftover downloads
            if os.path.exists("downloads") and os.path.isdir("downloads"):
                for file in os.listdir("downloads"):
                    try:
                        os.remove(os.path.join("downloads", file))
                    except:
                        pass
                        
            await self.client.disconnect()

async def main():
    """Main function to run the cloner"""
    try:
        print("Starting Telegram Cloner...")
        print(f"Source: {SOURCE_ENTITY}")
        print(f"Destination: {DESTINATION_ENTITY}")
        print(f"Maximum messages to clone: {'Unlimited' if MAX_MESSAGES == 0 else MAX_MESSAGES}")
        print(f"Delay between messages: {DELAY_BETWEEN_MESSAGES} seconds")
        print("Initializing...")
        
        cloner = TelegramCloner()
        stats = await cloner.start_cloning()
        
        print("\n===== Cloning Completed! =====")
        print(f"Total messages processed: {stats['total']}")
        print(f"Successfully cloned: {stats['cloned']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Failed: {stats['failed']}")
        print("\nContent types:")
        print(f"Photos: {stats['photos']}")
        print(f"Videos: {stats['videos']}")
        print(f"Files: {stats['files']}")
        print(f"Voice messages: {stats['voices']}")
        print(f"Music: {stats['music']}")
        print(f"GIFs: {stats['gifs']}")
        print(f"Stickers: {stats['stickers']}")
        print(f"Polls: {stats['polls']}")
        print(f"Contacts: {stats['contacts']}")
        print(f"Albums: {stats['albums']}")
        print(f"Forwards: {stats['forwards']}")
        print(f"Text only: {stats['text_only']}")
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        return 130
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        print(f"\nCritical error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        exit(exit_code)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        exit(130)