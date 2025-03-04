import time
import asyncio
from telethon.sync import TelegramClient
from telethon import errors
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import Channel

class TelegramForwarder:
    def __init__(self, api_id, api_hash, phone_number):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.client = TelegramClient('session_' + phone_number, api_id, api_hash)

    async def list_chats(self):
        await self.client.connect()

        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.phone_number)
            try:
                await self.client.sign_in(self.phone_number, input('🔑Enter the code: '))
            except errors.rpcerrorlist.SessionPasswordNeededError:
                password = input('🔑Two-step verification is enabled. Enter your password: ')
                await self.client.sign_in(password=password)

        dialogs = await self.client.get_dialogs(limit=None)
        with open(f"chats_of_{self.phone_number}.txt", "w", encoding="utf-8") as chats_file:
            for dialog in dialogs:
                chats_file.write(f"💬 MAIN CHAT ID: {dialog.id}, Title: {dialog.title}\n")
                print(f"💬 MAIN CHAT ID: {dialog.id}, Title: {dialog.title}")

                if isinstance(dialog.entity, Channel) and getattr(dialog.entity, 'forum', False):
                    try:
                        topics = await self.client(GetForumTopicsRequest(
                            channel=dialog.entity,
                            offset_date=0,
                            offset_id=0,
                            offset_topic=0,
                            limit=100
                        ))
                        for topic in topics.topics:
                            chats_file.write(f"    🗂️ TOPIC ID: {dialog.id}/{topic.id}, Title: {topic.title}\n")
                            print(f"    🗂️ TOPIC ID: {dialog.id}/{topic.id}, Title: {topic.title}")
                    except Exception as e:
                        print(f"⚠️ Error fetching topics for {dialog.title}: {e}")

        print("✅List of groups and topics printed successfully!")

    async def send_message_periodically(self, destination_chat_ids, text, image_path=None):
        await self.client.connect()

        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.phone_number)
            await self.client.sign_in(self.phone_number, input('🔑Enter the code: '))

        while True:
            for raw_chat_id in destination_chat_ids:
                chat_id = raw_chat_id.strip()
                try:
                    if "/" in chat_id:
                        group_id, topic_id = chat_id.split("/")
                        entity = await self.client.get_entity(int(group_id))
                        send_params = {
                            "entity": entity,
                            "message": text,
                            "reply_to": int(topic_id)  # Targetkan ke topik forum
                        }
                    else:
                        entity = await self.client.get_entity(int(chat_id))
                        send_params = {"entity": entity, "message": text}

                    if image_path:
                        await self.client.send_file(**send_params, file=image_path, caption=text)
                        print(f"🚀Sent message with image to {chat_id}")
                    else:
                        await self.client.send_message(**send_params)
                        print(f"🚀Sent message to {chat_id}")

                except Exception as e:
                    print(f"❌ Gagal mengirim ke {chat_id}: {str(e)}")

            print("⏳Waiting 5 minutes before sending again...")
            await asyncio.sleep(300)

def read_credentials():
    try:
        with open("credentials.txt", "r") as file:
            lines = file.readlines()
            api_id = lines[0].strip()
            api_hash = lines[1].strip()
            phone_number = lines[2].strip()
            return api_id, api_hash, phone_number
    except FileNotFoundError:
        print("❌Credentials file not found.")
        return None, None, None

def write_credentials(api_id, api_hash, phone_number):
    with open("credentials.txt", "w") as file:
        file.write(api_id + "\n")
        file.write(api_hash + "\n")
        file.write(phone_number + "\n")

async def main():
    api_id, api_hash, phone_number = read_credentials()

    if api_id is None or api_hash is None or phone_number is None:
        api_id = input("🔑Enter your API ID: ")
        api_hash = input("🔑Enter your API Hash: ")
        phone_number = input("🔑Enter your phone number: ")
        write_credentials(api_id, api_hash, phone_number)

    forwarder = TelegramForwarder(api_id, api_hash, phone_number)
    
    print("AUTOMATIC SENDER TOOLS BY dippfles 😒👌")
    print("Choose an option:")
    print("1. List Chats")
    print("2. Forward Messages to One Chat")
    print("3. Forward Messages to Multiple Chats")
    print("4. Send Message (Text/Image) to Multiple Chats Periodically")

    choice = input("Enter your choice: ")

    if choice == "1":
        await forwarder.list_chats()
    elif choice == "4":
        destination_chat_ids = input("🪄Enter destination chat IDs (comma separated): ").split(",")
        text = input("🕛Enter the text to send every 5 minutes: ")
        
        send_image = input("🏳️Do you want to send an image? (yes/no): ").strip().lower()
        image_path = None
        if send_image == "yes":
            image_path = input("🏳️Enter the image file path: ").strip()

        await forwarder.send_message_periodically(destination_chat_ids, text, image_path)
    else:
        print("Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())
