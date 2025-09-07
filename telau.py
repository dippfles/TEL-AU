import time
import asyncio
import os
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

    async def login(self):
        """Handle login process and save session"""
        print("🔐 Starting login process...")
        await self.client.connect()

        if await self.client.is_user_authorized():
            print("✅ Already logged in!")
            return True

        try:
            print(f"📱 Sending verification code to {self.phone_number}...")
            await self.client.send_code_request(self.phone_number)
            
            code = input('🔑Enter the verification code: ')
            await self.client.sign_in(self.phone_number, code)
            
        except errors.rpcerrorlist.SessionPasswordNeededError:
            password = input('🔑Two-step verification is enabled. Enter your password: ')
            await self.client.sign_in(password=password)
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

        print("✅ Login successful! Session saved.")
        return True

    async def check_session(self):
        """Check if session exists and is valid"""
        try:
            await self.client.connect()
            if await self.client.is_user_authorized():
                me = await self.client.get_me()
                print(f"✅ Session is valid. Logged in as: {me.first_name} (@{me.username or 'No username'})")
                return True
            else:
                print("❌ Session exists but not authorized.")
                return False
        except Exception as e:
            print(f"❌ Session check failed: {e}")
            return False

    async def list_chats(self):
        await self.client.connect()

        # Session should already be validated before calling this
        if not await self.client.is_user_authorized():
            print("❌ Not authorized. Please login first.")
            return

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

    async def validate_chat_id(self, chat_id):
        """Validate if chat ID is accessible"""
        try:
            chat_id = chat_id.strip()
            if "/" in chat_id:
                group_id, topic_id = chat_id.split("/")
                entity = await self.client.get_entity(int(group_id))
                # Check if it's a valid forum topic
                if hasattr(entity, 'forum') and entity.forum:
                    return True, entity, int(topic_id)
                else:
                    return False, None, None
            else:
                entity = await self.client.get_entity(int(chat_id))
                return True, entity, None
        except Exception as e:
            return False, None, None

    async def send_to_single_chat(self, chat_id, text, image_path, interval_seconds):
        """Send messages to a single chat with its specific interval"""
        # First validate the chat ID
        is_valid, entity, topic_id = await self.validate_chat_id(chat_id)
        
        if not is_valid:
            print(f"❌ Chat ID {chat_id} is invalid or not accessible. Skipping this chat.")
            print(f"   Common causes:")
            print(f"   - Chat ID doesn't exist")
            print(f"   - You're not a member of the group")
            print(f"   - Bot restrictions (if applicable)")
            print(f"   - Wrong ID format")
            return
        
        print(f"✅ Chat {chat_id} validated successfully. Starting periodic sending...")
        
        while True:
            try:
                chat_id = chat_id.strip()
                if topic_id is not None:  # Forum topic
                    send_params = {
                        "entity": entity,
                        "message": text,
                        "reply_to": topic_id
                    }
                else:  # Regular chat
                    send_params = {"entity": entity, "message": text}

                if image_path:
                    await self.client.send_file(**send_params, file=image_path, caption=text)
                    print(f"🚀Sent message with image to {chat_id}")
                else:
                    await self.client.send_message(**send_params)
                    print(f"🚀Sent message to {chat_id}")

            except errors.FloodWaitError as e:
                print(f"⚠️ Rate limit hit for {chat_id}. Waiting {e.seconds} seconds...")
                await asyncio.sleep(e.seconds)
                continue
            except errors.ChatWriteForbiddenError:
                print(f"❌ No permission to write in chat {chat_id}. Stopping this chat.")
                break
            except errors.UserBannedInChannelError:
                print(f"❌ You are banned in chat {chat_id}. Stopping this chat.")
                break
            except errors.PeerIdInvalidError:
                print(f"❌ Invalid peer ID {chat_id}. Stopping this chat.")
                break
            except Exception as e:
                print(f"❌ Error sending to {chat_id}: {str(e)}")
                # Continue trying for other types of errors
                await asyncio.sleep(10)  # Wait 10 seconds before retry

            # Convert seconds to readable format for display
            hours = interval_seconds // 3600
            minutes = (interval_seconds % 3600) // 60
            seconds = interval_seconds % 60
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                time_str = f"{minutes}m {seconds}s"
            else:
                time_str = f"{seconds}s"
                
            current_time = time.strftime("%H:%M:%S")
            print(f"⏳[{current_time}] Chat {chat_id}: Waiting {time_str} before next send...")
            await asyncio.sleep(interval_seconds)

    async def send_message_periodically_multi_interval(self, chat_configs, text, image_path=None):
        """Send messages to multiple chats with different intervals for each"""
        await self.client.connect()

        # Session should already be validated before calling this
        if not await self.client.is_user_authorized():
            print("❌ Not authorized. Please login first.")
            return

        # Create tasks for each chat with their specific intervals
        tasks = []
        for chat_id, interval_seconds in chat_configs.items():
            task = asyncio.create_task(
                self.send_to_single_chat(chat_id, text, image_path, interval_seconds)
            )
            tasks.append(task)

        # Run all tasks concurrently
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\n🛑 Stopping all sending tasks...")
            for task in tasks:
                task.cancel()

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

def check_session_file_exists(phone_number):
    """Check if session file exists"""
    session_file = f"session_{phone_number}.session"
    return os.path.exists(session_file)

def read_text_from_file(file_path):
    """Read text content from a file"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read().strip()
            if not content:
                print(f"⚠️ Warning: File '{file_path}' is empty.")
                return None
            return content
    except FileNotFoundError:
        print(f"❌ Error: File '{file_path}' not found.")
        return None
    except Exception as e:
        print(f"❌ Error reading file '{file_path}': {e}")
        return None

def show_login_menu():
    """Show login menu options"""
    print("\n🔐 LOGIN REQUIRED")
    print("You need to login first before using other features.")
    print("\nChoose an option:")
    print("1. Login to Telegram")
    print("2. Exit")
    return input("Enter your choice: ").strip()

def show_main_menu():
    """Show main menu options"""
    print("\nAUTOMATIC SENDER TOOLS BY dippfles 😒👌")
    print("Choose an option:")
    print("1. List Chats")
    print("2. Send Message (Text/Image) to Multiple Chats with Custom Intervals")
    print("3. Send Message from Text File to Multiple Chats with Custom Intervals")
    print("4. Logout")
    print("5. Exit")
    return input("Enter your choice: ").strip()

def get_time_interval_for_chat(chat_id):
    """Get custom time interval for a specific chat"""
    print(f"\n⏰ Set time interval for Chat ID: {chat_id}")
    print("1. Enter in seconds")
    print("2. Enter in minutes")
    print("3. Enter in hours")
    print("4. Custom (hours, minutes, seconds)")
    
    choice = input(f"Enter choice for {chat_id} (1-4): ").strip()
    
    if choice == "1":
        seconds = int(input(f"Enter interval in seconds for {chat_id}: "))
        return seconds
    elif choice == "2":
        minutes = int(input(f"Enter interval in minutes for {chat_id}: "))
        return minutes * 60
    elif choice == "3":
        hours = int(input(f"Enter interval in hours for {chat_id}: "))
        return hours * 3600
    elif choice == "4":
        hours = int(input(f"Enter hours for {chat_id} (0 if none): ") or "0")
        minutes = int(input(f"Enter minutes for {chat_id} (0 if none): ") or "0")
        seconds = int(input(f"Enter seconds for {chat_id} (0 if none): ") or "0")
        return hours * 3600 + minutes * 60 + seconds
    else:
        print("Invalid choice, defaulting to 5 minutes")
        return 300

def setup_chat_configs():
    """Setup chat configurations with individual time intervals"""
    destination_chat_ids = input("🪄Enter destination chat IDs (comma separated): ").split(",")
    chat_configs = {}
    
    print(f"\n📋 Setting up intervals for {len(destination_chat_ids)} chat(s)...")
    print("💡 Tips for Chat ID:")
    print("   - Use positive numbers for private chats/users")
    print("   - Use negative numbers for groups/channels") 
    print("   - For forum topics: use format 'GROUP_ID/TOPIC_ID'")
    print("   - Make sure you're a member of the group/channel")
    
    valid_chats = []
    for i, chat_id in enumerate(destination_chat_ids, 1):
        chat_id = chat_id.strip()
        print(f"\n--- Configuration for Chat {i}/{len(destination_chat_ids)} ---")
        print(f"Chat ID: {chat_id}")
        
        # Ask user if they want to continue with this chat ID
        confirm = input(f"Continue with this Chat ID? (y/n): ").strip().lower()
        if confirm != 'y':
            print(f"Skipping Chat ID: {chat_id}")
            continue
            
        interval = get_time_interval_for_chat(chat_id)
        chat_configs[chat_id] = interval
        valid_chats.append(chat_id)
        
        # Show confirmation
        hours = interval // 3600
        minutes = (interval % 3600) // 60
        seconds = interval % 60
        
        if hours > 0:
            time_str = f"{hours} hours, {minutes} minutes, {seconds} seconds"
        elif minutes > 0:
            time_str = f"{minutes} minutes, {seconds} seconds"
        else:
            time_str = f"{seconds} seconds"
            
        print(f"✅ Chat {chat_id} will send every {time_str}")
    
    if not chat_configs:
        print("❌ No valid chat configurations created!")
        return None
        
    print(f"\n📊 Summary: {len(chat_configs)} chat(s) configured successfully")
    return chat_configs

async def main():
    api_id, api_hash, phone_number = read_credentials()

    if api_id is None or api_hash is None or phone_number is None:
        print("🔧 INITIAL SETUP")
        api_id = input("🔑Enter your API ID: ")
        api_hash = input("🔑Enter your API Hash: ")
        phone_number = input("🔑Enter your phone number (with country code): ")
        write_credentials(api_id, api_hash, phone_number)
        print("✅ Credentials saved!")

    forwarder = TelegramForwarder(api_id, api_hash, phone_number)
    
    # Check if session exists and is valid
    session_exists = check_session_file_exists(phone_number)
    session_valid = False
    
    if session_exists:
        print("📱 Checking existing session...")
        session_valid = await forwarder.check_session()
    
    # Main application loop
    while True:
        if not session_valid:
            # Show login menu
            choice = show_login_menu()
            
            if choice == "1":
                if await forwarder.login():
                    session_valid = True
                    print("🎉 You can now use all features!")
                else:
                    print("❌ Login failed. Please try again.")
            elif choice == "2":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please try again.")
        else:
            # Show main menu
            choice = show_main_menu()
            
            if choice == "1":
                print("\n📋 LISTING CHATS...")
                await forwarder.list_chats()
                
            elif choice == "2":
                print("\n🚀 MESSAGE SENDER...")
                # Setup chat configurations with individual intervals
                chat_configs = setup_chat_configs()
                
                if chat_configs is None:
                    print("❌ No chat configurations available.")
                    continue
                
                text = input("\n📝Enter the text to send: ")
                
                send_image = input("🏳️Do you want to send an image? (yes/no): ").strip().lower()
                image_path = None
                if send_image == "yes":
                    image_path = input("🏳️Enter the image file path: ").strip()
                    # Validate image path
                    if not os.path.exists(image_path):
                        print(f"⚠️ Warning: Image file '{image_path}' not found. Continuing with text only.")
                        image_path = None

                print(f"\n🚀 Starting to send messages to {len(chat_configs)} chat(s) with different intervals...")
                print("💡 Note: Invalid chat IDs will be automatically skipped after validation")
                print("Press Ctrl+C to stop all sending tasks")
                
                try:
                    await forwarder.send_message_periodically_multi_interval(chat_configs, text, image_path)
                except KeyboardInterrupt:
                    print("\n⏹️ Stopped by user.")
                    
            elif choice == "3":
                print("\n📄 MESSAGE SENDER FROM TEXT FILE...")
                # Setup chat configurations with individual intervals
                chat_configs = setup_chat_configs()
                
                if chat_configs is None:
                    print("❌ No chat configurations available.")
                    continue
                
                # Get text file path
                file_path = input("\n📁Enter the path to your text file (.txt): ").strip()
                
                # Read text from file
                text = read_text_from_file(file_path)
                if text is None:
                    print("❌ Could not read text from file. Operation cancelled.")
                    continue
                
                print(f"✅ Successfully loaded text from file:")
                print(f"📝 Text preview (first 100 characters): {text[:100]}{'...' if len(text) > 100 else ''}")
                print(f"📊 Total characters: {len(text)}")
                
                # Confirm before sending
                confirm = input("\n❓Proceed with sending this text? (yes/no): ").strip().lower()
                if confirm != "yes":
                    print("❌ Operation cancelled.")
                    continue
                
                send_image = input("🏳️Do you want to send an image with the text? (yes/no): ").strip().lower()
                image_path = None
                if send_image == "yes":
                    image_path = input("🏳️Enter the image file path: ").strip()
                    # Validate image path
                    if not os.path.exists(image_path):
                        print(f"⚠️ Warning: Image file '{image_path}' not found. Continuing with text only.")
                        image_path = None

                print(f"\n🚀 Starting to send messages from file to {len(chat_configs)} chat(s) with different intervals...")
                print("💡 Note: Invalid chat IDs will be automatically skipped after validation")
                print("Press Ctrl+C to stop all sending tasks")
                
                try:
                    await forwarder.send_message_periodically_multi_interval(chat_configs, text, image_path)
                except KeyboardInterrupt:
                    print("\n⏹️ Stopped by user.")
                    
            elif choice == "4":
                print("\n🚪 LOGOUT...")
                # Delete session file
                session_file = f"session_{phone_number}.session"
                try:
                    if os.path.exists(session_file):
                        os.remove(session_file)
                    if os.path.exists(session_file + "-journal"):
                        os.remove(session_file + "-journal")
                    print("✅ Logged out successfully!")
                    session_valid = False
                except Exception as e:
                    print(f"⚠️ Error during logout: {e}")
                    
            elif choice == "5":
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please try again.")
                
        print()  # Add blank line for better readability

if __name__ == "__main__":
    asyncio.run(main())
