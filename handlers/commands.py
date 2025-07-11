# handlers/commands.py
import logging
import os
import re
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import jenkins

import database
import security
import config
from timeout_handler import TimeoutConversationHandler

logger = logging.getLogger(__name__)

# Định nghĩa các trạng thái
GET_URL, GET_USERID, GET_TOKEN, GET_DOCUMENT_LINK = range(4)

# Định nghĩa key cho document link trong bảng settings
DOCUMENT_LINK_KEY = "document_link"

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gửi tin nhắn chào mừng tùy theo trạng thái đăng nhập."""
    user = update.effective_user
    logger.info(f"Received /start command from {user.first_name} (ID: {user.id})")
    if database.is_user_logged_in(user.id):
        welcome_message = (
            f"Hi {user.mention_html()}! You are already logged in.\n\n"
            "You can use these commands:\n"
            "  /setup - (In a group) Link a group to a Jenkins job\n"
            "  /build - (In a group) Start a new build\n"
            "  /logout - Disconnect your Jenkins account\n"
            "  /document - Show documentation link\n"
            "  /setdocument - Update documentation link (admin only)\n"
            "  /help - Show this message again"
        )
    else:
        welcome_message = (
            f"Hi {user.mention_html()}! Welcome to the Jenkins Bot.\n\n"
            "Please use /login to connect your Jenkins account."
        )
    await update.message.reply_html(welcome_message)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gửi tin nhắn trợ giúp."""
    user = update.effective_user
    logger.info(f"Received /help command from {user.first_name} (ID: {user.id})")
    await start_handler(update, context)

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gửi link document từ cơ sở dữ liệu."""
    user = update.effective_user
    logger.info(f"Received /document command from {user.first_name} (ID: {user.id})")
    
    # Lấy link document từ cơ sở dữ liệu
    document_link = database.get_setting_value(DOCUMENT_LINK_KEY)
    
    if document_link:
        await update.message.reply_text(
            f"📚 Documentation: {document_link}",
            disable_web_page_preview=False
        )
    else:
        await update.message.reply_text(
            "❌ Documentation link is not configured. Please ask an admin to set it up using /setdocument."
        )

async def setdocument_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bắt đầu quá trình cập nhật link document."""
    user = update.effective_user
    logger.info(f"Received /setdocument command from {user.first_name} (ID: {user.id})")
    
    # Kiểm tra quyền admin (có thể thay đổi logic này theo nhu cầu)
    # Ví dụ: chỉ cho phép một số user_id nhất định
    admin_ids = getattr(config, 'ADMIN_IDS', [])
    if not admin_ids or user.id not in admin_ids:
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return ConversationHandler.END
    
    # Hiển thị link hiện tại nếu có
    current_link = database.get_setting_value(DOCUMENT_LINK_KEY)
    message_text = ""
    if current_link:
        message_text = f"Current documentation link: {current_link}\n\nPlease send the new documentation link:"
    else:
        message_text = "Please send the documentation link:"
    
    # Gửi tin nhắn và lưu message_id để xử lý timeout
    message = await update.message.reply_text(message_text)
    
    # Lưu metadata cho timeout handler
    context.user_data['owner_id'] = user.id  # Lưu ID người dùng để kiểm tra quyền
    TimeoutConversationHandler.set_timeout_metadata(
        context, message.chat_id, message.message_id, "setdocument"
    )
    
    return GET_DOCUMENT_LINK

async def set_document_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lưu link document mới vào cơ sở dữ liệu."""
    new_link = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Kiểm tra tính hợp lệ của link
    if not new_link.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Invalid link. Please provide a valid URL starting with http:// or https://")
        return GET_DOCUMENT_LINK
    
    try:
        # Lưu link vào cơ sở dữ liệu
        if database.save_setting(DOCUMENT_LINK_KEY, new_link, user_id):
            await update.message.reply_text(f"✅ Documentation link updated successfully to:\n{new_link}")
        else:
            await update.message.reply_text("❌ Failed to update documentation link. Please try again later.")
    except Exception as e:
        logger.error(f"Error updating document link: {e}")
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")
    
    # Xóa timeout metadata khi hoàn thành thành công
    TimeoutConversationHandler.clear_timeout_metadata(context)
    
    return ConversationHandler.END

async def cancel_setdocument(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hủy quá trình cập nhật link document."""
    await update.message.reply_text("Process canceled.")
    
    # Xóa timeout metadata khi hủy
    TimeoutConversationHandler.clear_timeout_metadata(context)
    
    return ConversationHandler.END

async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Đăng xuất người dùng."""
    user = update.effective_user
    logger.info(f"Received /logout command from {user.first_name} (ID: {user.id})")
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this command in a private chat with me.")
        return

    user_id = update.effective_user.id
    if database.is_user_logged_in(user_id):
        database.delete_user(user_id)
        await update.message.reply_text("You have been successfully logged out.")
    else:
        await update.message.reply_text("You are not logged in.")

# --- Login Conversation ---

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bắt đầu cuộc hội thoại login."""
    user = update.effective_user
    logger.info(f"Received /login command from {user.first_name} (ID: {user.id})")
    user_id = update.effective_user.id
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this command in a private chat with me for security.")
        return ConversationHandler.END

    if database.is_user_logged_in(user_id):
        await update.message.reply_text("You are already logged in. Use /logout first to switch accounts.")
        return ConversationHandler.END

    await update.message.reply_text("What is your Jenkins server URL? (e.g., https://jenkins.example.com)")
    return GET_URL

async def get_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lưu URL và hỏi User ID."""
    context.user_data['jenkins_url'] = update.message.text.strip()
    await update.message.reply_text("What's your Jenkins User ID?")
    return GET_USERID

async def get_userid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lưu User ID và hỏi API Token."""
    context.user_data['jenkins_userid'] = update.message.text.strip()
    await update.message.reply_text("What's your Jenkins API Token?")
    return GET_TOKEN

async def get_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xác thực và lưu thông tin đăng nhập."""
    jenkins_url = context.user_data.get('jenkins_url')
    jenkins_userid = context.user_data.get('jenkins_userid')
    jenkins_token = update.message.text.strip()
    
    await update.message.reply_text("Verifying credentials...")
    try:
        server = jenkins.Jenkins(jenkins_url, username=jenkins_userid, password=jenkins_token, timeout=10)
        user_info = server.get_whoami()
        encrypted_token = security.encrypt_data(jenkins_token)
        database.save_user(update.effective_user.id, jenkins_url, jenkins_userid, encrypted_token)
        await update.message.reply_text(f"✅ Success! Connected as '{user_info.get('fullName', 'Unknown User')}'.")
    except Exception as e:
        await update.message.reply_text(f"❌ Authentication failed: {e}. Please use /login to try again.")
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hủy cuộc hội thoại."""
    await update.message.reply_text("Process canceled.")
    context.user_data.clear()
    return ConversationHandler.END
