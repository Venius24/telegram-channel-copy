from keys import API_ID, API_HASH
from pyrogram import Client
from typing import AsyncGenerator
from pyrogram.types import Message
import asyncio
from pyrogram.errors import FloodWait, BadMsgNotification
from random import randint


async def get_all_messages(client: Client, chat_id: str, limit_per_request: int = 100) -> list:
    """Получает все сообщения с начала истории чата."""
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
        print(f"Получено {len(messages_list)} сообщений, текущий offset_id: {offset_id}")

    return all_messages


async def split_caption(caption: str, max_length: int = 1024) -> list:
    """Разбивает длинную подпись на части по max_length символов."""
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
    """Callback-функция для отображения прогресса загрузки."""
    percent = (current / total) * 100
    print(f"Загрузка {media_type} ID {message_id}: {percent:.2f}% ({current} из {total} байт)")


async def clone_content(donor_channel_id: str, my_channel_id: int, start_message_id: int = None):
    if not donor_channel_id or not my_channel_id:
        raise ValueError("donor_channel_id and my_channel_id must not be empty")

    async with Client(name="my_session", api_id=API_ID, api_hash=API_HASH) as client:
        print(f"Копируем из чата {donor_channel_id} в чат {my_channel_id}" + 
              (f", начиная с ID {start_message_id}" if start_message_id else ""))

        # Проверяем donor_channel_id
        try:
            donor_chat = await client.get_chat(donor_channel_id)
            print(f"Donor chat: {donor_chat.title} (ID: {donor_chat.id})")
        except Exception as e:
            print(f"Ошибка с donor_channel_id '{donor_channel_id}': {e}")
            return

        # Проверяем my_channel_id
        try:
            my_chat = await client.get_chat(my_channel_id)
            print(f"My chat: {my_chat.title} (ID: {my_chat.id})")
        except Exception as e:
            print(f"Ошибка с my_channel_id '{my_channel_id}': {e}")
            return

        # Тестовое сообщение в my_channel_id с обработкой FloodWait
        try:
            test_message = await client.send_message(my_channel_id, "Тестовое сообщение от бота")
            print(f"Тестовое сообщение отправлено в {my_channel_id}: {test_message.id}")
            await test_message.delete()
        except FloodWait as e:
            wait_time = e.value
            print(f"Слишком много запросов при отправке теста. Ждём {wait_time} секунд...")
            await asyncio.sleep(wait_time)
            test_message = await client.send_message(my_channel_id, "Тестовое сообщение от бота")
            print(f"Тестовое сообщение отправлено в {my_channel_id}: {test_message.id}")
            await test_message.delete()
        except Exception as e:
            print(f"Не удалось отправить тестовое сообщение в {my_channel_id}: {e}")
            return

        # Получаем все сообщения с начала истории
        all_messages = await get_all_messages(client, donor_channel_id, limit_per_request=50)
        print(f"Всего найдено {len(all_messages)} сообщений")

        # Переворачиваем порядок сообщений (от новых к старым)
        reversed_messages = all_messages[::-1]

        # Фильтруем сообщения, начиная с start_message_id
        if start_message_id:
            reversed_messages = [msg for msg in reversed_messages if msg.id > start_message_id]
            print(f"После фильтрации осталось {len(reversed_messages)} сообщений, начиная с ID {start_message_id + 1}")

        # Копируем сообщения в обратном порядке
        for message in reversed_messages:
            try:
                # Получаем подпись или текст и разбиваем на части
                content = message.text or (message.caption.html if message.caption else "")
                content_parts = await split_caption(content, max_length=1024)

                # Отправляем основной контент с первой частью
                if message.video:
                    for attempt in range(3):
                        try:
                            video = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "видео")
                            )
                            await client.send_video(
                                chat_id=my_channel_id,
                                video=video,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Скопировано видео ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"Ошибка msg_seqno для видео ID {message.id}: {e}. Повтор через 5 секунд...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Ошибка загрузки видео ID {message.id}: {e}")
                            break
                elif message.photo:
                    for attempt in range(3):
                        try:
                            photo = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "фото")
                            )
                            await client.send_photo(
                                chat_id=my_channel_id,
                                photo=photo,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Скопировано фото ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"Ошибка msg_seqno для фото ID {message.id}: {e}. Повтор через 5 секунд...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Ошибка загрузки фото ID {message.id}: {e}")
                            break
                elif message.audio:
                    for attempt in range(3):
                        try:
                            audio = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "аудио")
                            )
                            await client.send_audio(
                                chat_id=my_channel_id,
                                audio=audio,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Скопировано аудио ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"Ошибка msg_seqno для аудио ID {message.id}: {e}. Повтор через 5 секунд...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Ошибка загрузки аудио ID {message.id}: {e}")
                            break
                elif message.document:
                    for attempt in range(3):
                        try:
                            document = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "документ")
                            )
                            await client.send_document(
                                chat_id=my_channel_id,
                                document=document,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Скопирован документ ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"Ошибка msg_seqno для документа ID {message.id}: {e}. Повтор через 5 секунд...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Ошибка загрузки документа ID {message.id}: {e}")
                            break
                elif message.voice:
                    for attempt in range(3):
                        try:
                            voice = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "голосовое сообщение")
                            )
                            await client.send_voice(
                                chat_id=my_channel_id,
                                voice=voice,
                                caption=content_parts[0] if content_parts else ""
                            )
                            print(f"Скопировано голосовое сообщение ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"Ошибка msg_seqno для голосового сообщения ID {message.id}: {e}. Повтор через 5 секунд...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Ошибка загрузки голосового сообщения ID {message.id}: {e}")
                            break
                elif message.video_note:
                    for attempt in range(3):
                        try:
                            video_note = await message.download(
                                in_memory=True,
                                progress=progress_callback,
                                progress_args=(message.id, "видео-заметка")
                            )
                            await client.send_video_note(
                                chat_id=my_channel_id,
                                video_note=video_note
                            )
                            print(f"Скопирована видео-заметка ID {message.id}")
                            break
                        except BadMsgNotification as e:
                            print(f"Ошибка msg_seqno для видео-заметки ID {message.id}: {e}. Повтор через 5 секунд...")
                            await asyncio.sleep(5)
                        except Exception as e:
                            print(f"Ошибка загрузки видео-заметки ID {message.id}: {e}")
                            break
                elif content_parts:  # Отправляем текст только если он есть
                    await client.send_message(
                        chat_id=my_channel_id,
                        text=content_parts[0]
                    )
                    print(f"Скопирован текст ID {message.id}")
                else:
                    print(f"Пропущено сообщение ID {message.id} — нет содержимого")

                # Отправляем остальные части как отдельные сообщения
                for part in content_parts[1:]:
                    await asyncio.sleep(randint(6, 20))
                    await client.send_message(
                        chat_id=my_channel_id,
                        text=part
                    )
                    print(f"Отправлена дополнительная часть для сообщения ID {message.id}")

                # Задержка между отправками сообщений
                await asyncio.sleep(randint(6, 20))

            except FloodWait as e:
                wait_time = e.value
                print(f"Слишком много запросов. Ждём {wait_time} секунд...")
                await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                print(f"Ошибка при копировании сообщения ID {message.id}: {e}")

if __name__ == "__main__":
    donor_channel = "-1001629147115"  # Рабочий ID как строка
    my_channel = -1002673775019       # Целевой ID как число
    start_message_id = 6529         # Начинаем с ID 351 (после 350)
    try:
        asyncio.run(clone_content(donor_channel_id=donor_channel, 
                                 my_channel_id=my_channel, 
                                 start_message_id=start_message_id))
    except FloodWait as e:
        print(f"Слишком много запросов на верхнем уровне. Ждём {e.value} секунд и перезапускаем...")
        asyncio.sleep(e.value)
        asyncio.run(clone_content(donor_channel_id=donor_channel, 
                                 my_channel_id=my_channel, 
                                 start_message_id=start_message_id))
    except Exception as e:
        print(f"Произошла ошибка: {e}")