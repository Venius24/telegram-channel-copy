from keys import API_ID, API_HASH, MY_CHANNEL, DONOR_CHANNEL, START_MESSAGE_ID
from pyrogram import Client
from typing import AsyncGenerator
from pyrogram.types import Message
import asyncio
from pyrogram.errors import FloodWait, BadMsgNotification
from random import randint


async def get_all_messages(client: Client, chat_id: str, limit_per_request: int = 100) -> list:
    """Retrieve all messages from the start of the channel/chat."""
    all_messages = []
    offset_id = 0

    while True:
        messages: AsyncGenerator[Message, None] = client.get_chat_history(
            chat_id=chat_id,
            limit=limit_per_request,
            offset_id=offset_id
        )
        messages_list = [message async for message in messages]

        if not messages_list:
            break

        all_messages.extend(messages_list)
        offset_id = messages_list[-1].id
        print(f"Retrieved {len(messages_list)} messages, current offset_id: {offset_id}")

    return all_messages


async def split_caption(caption: str, max_length: int = 1024) -> list:
    """Splits a long caption into parts of max_length characters."""
    if not caption or len(caption) <= max_length:
        return [caption] if caption else []
    
    parts = []
    while caption:
        if len(caption) <= max_length:
            parts.append(caption)
            break
        split_pos = caption[:max_length].rfind(" ")
        if split_pos == -1:
            split_pos = max_length
        parts.append(caption[:split_pos])
        caption = caption[split_pos:].strip()
    return parts


async def progress_callback(current: int, total: int, message_id: int, media_type: str):
    """Callback function to display upload progress."""
    percent = (current / total) * 100
    print(f"Uploading {media_type} ID {message_id}: {percent:.2f}% ({current} of {total} bytes)")


async def clone_content(donor_channel_id: str, my_channel_id: int, start_message_id: int = None):
    if not donor_channel_id or not my_channel_id:
        raise ValueError("donor_channel_id and my_channel_id must not be empty")

    async with Client(name="my_session", api_id=API_ID, api_hash=API_HASH) as client:
        print(f"Copying from chat {donor_channel_id} to chat {my_channel_id}" + 
              (f", starting from ID {start_message_id}" if start_message_id else ""))

        # Check donor_channel_id
        try:
            donor_chat = await client.get_chat(donor_channel_id)
            print(f"Donor chat: {donor_chat.title} (ID: {donor_chat.id})")
        except Exception as e:
            print(f"Error with donor_channel_id '{donor_channel_id}': {e}")
            return

        # Check my_channel_id
        try:
            my_chat = await client.get_chat(my_channel_id)
            print(f"My chat: {my_chat.title} (ID: {my_chat.id})")
        except Exception as e:
            print(f"Error with my_channel_id '{my_channel_id}': {e}")
            return

        # Test message in my_channel_id with FloodWait handling
        try:
            test_message = await client.send_message(my_channel_id, "Test message from bot")
            print(f"Test message sent to {my_channel_id}: {test_message.id}")
            await test_message.delete()
        except FloodWait as e:
            wait_time = e.value
            print(f"Too many requests during test message. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            test_message = await client.send_message(my_channel_id, "Test message from bot")
            print(f"Test message sent to {my_channel_id}: {test_message.id}")
            await test_message.delete()
        except Exception as e:
            print(f"Failed to send test message to {my_channel_id}: {e}")
            return

        # Retrieve all messages from the beginning of history
        all_messages = await get_all_messages(client, donor_channel_id, limit_per_request=50)
        print(f"Found {len(all_messages)} messages in total")

        # Reverse the order of messages (from newest to oldest)
        reversed_messages = all_messages[::-1]

        # Filter messages starting from start_message_id
        if start_message_id:
            reversed_messages = [msg for msg in reversed_messages if msg.id > start_message_id]
            print(f"After filtering, {len(reversed_messages)} messages remain, starting from ID {start_message_id + 1}")

        # Copy messages in reverse order
        for message in reversed_messages:
            try:
                # Get caption or text and split into parts
                content = message.text or (message.caption.html if message.caption else "")
                content_parts = await split_caption(content, max_length=1024)

                # Send main content with the first part
                if message.video:
                    for attempt in range(3):
                        try:
                            video = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "video")
                            )
                            await client.send_video(
                                chat_id=my_channel_id,
                                video=video,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Copied video ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"msg_seqno error for video ID {message.id}: {e}. Retrying in 5 seconds...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Error uploading video ID {message.id}: {e}")
                            break
                elif message.photo:
                    for attempt in range(3):
                        try:
                            photo = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "photo")
                            )
                            await client.send_photo(
                                chat_id=my_channel_id,
                                photo=photo,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Copied photo ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"msg_seqno error for photo ID {message.id}: {e}. Retrying in 5 seconds...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Error uploading photo ID {message.id}: {e}")
                            break
                elif message.audio:
                    for attempt in range(3):
                        try:
                            audio = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "audio")
                            )
                            await client.send_audio(
                                chat_id=my_channel_id,
                                audio=audio,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Copied audio ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"msg_seqno error for audio ID {message.id}: {e}. Retrying in 5 seconds...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Error uploading audio ID {message.id}: {e}")
                            break
                elif message.document:
                    for attempt in range(3):
                        try:
                            document = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "document")
                            )
                            await client.send_document(
                                chat_id=my_channel_id,
                                document=document,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Copied document ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"msg_seqno error for document ID {message.id}: {e}. Retrying in 5 seconds...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Error uploading document ID {message.id}: {e}")
                            break
                elif message.voice:
                    for attempt in range(3):
                        try:
                            voice = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "voice message")
                            )
                            await client.send_voice(
                                chat_id=my_channel_id,
                                voice=voice,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Copied voice message ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"msg_seqno error for voice message ID {message.id}: {e}. Retrying in 5 seconds...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Error uploading voice message ID {message.id}: {e}")
                            break
                elif message.video_note:
                    for attempt in range(3):
                        try:
                            video_note = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "video note")
                            )
                            await client.send_video_note(
                                chat_id=my_channel_id,
                                video_note=video_note
                            )
                            print(f"Copied video note ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"msg_seqno error for video note ID {message.id}: {e}. Retrying in 5 seconds...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Error uploading video note ID {message.id}: {e}")
                            break
                elif content_parts:  # Send text only if it exists
                    await client.send_message(
                        chat_id=my_channel_id,
                        text=content_parts[0]
                    )
                    print(f"Copied text ID {message.id}")
                else:
                    print(f"Skipped message ID {message.id} — no content")

                # Send remaining parts as separate messages
                for part in content_parts[1:]:
                    await asyncio.sleep(randint(6, 20))
                    await client.send_message(
                        chat_id=my_channel_id,
                        text=part
                    )
                    print(f"Sent additional part for message ID {message.id}")

                # Delay between sending messages
                await asyncio.sleep(randint(6, 20))

            except FloodWait as e:
                wait_time = e.value
                print(f"Too many requests. Waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                print(f"Error copying message ID {message.id}: {e}")

if __name__ == "__main__":
    donor_channel = "-1001629147115"  # Source channel ID as string
    my_channel = -1002673775019       # Target channel ID as integer
    start_message_id = 6529           # Start from this message ID (6529 + 1)
    try:
        asyncio.run(clone_content(donor_channel_id=donor_channel, 
                                 my_channel_id=my_channel, 
                                 start_message_id=start_message_id))
    except FloodWait as e:
        print(f"Too many requests at top level. Waiting {e.value} seconds and restarting...")
        asyncio.sleep(e.value)
        asyncio.run(clone_content(donor_channel_id=donor_channel, 
                                 my_channel_id=my_channel, 
                                 start_message_id=start_message_id))
    except Exception as e:
        print(f"An error occurred: {e}")
