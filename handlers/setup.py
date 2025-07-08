import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import jenkins

import database
import security
from timeout_handler import TimeoutConversationHandler

logger = logging.getLogger(__name__)

def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram's MarkdownV2 parse mode."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f"\\{char}" if char in escape_chars else char for char in text)

# Định nghĩa các trạng thái
SELECT_FOLDER, SELECT_JOB_IN_FOLDER = range(2)

async def setup_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gửi tin nhắn với nút bấm để bắt đầu cuộc hội thoại setup."""
    user = update.effective_user
    if not update.message or not user:
        return

    logger.info(f"Received /setup command from {user.first_name} (ID: {user.id}) in group '{update.message.chat.title}' (ID: {update.message.chat.id})")

    if update.message.chat.type == "private":
        await update.message.reply_text("This command only works in a group chat.")
        return
        
    keyboard = [
        [InlineKeyboardButton("🚀 Start Setup", callback_data="start_setup")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup_initial")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Click the button to begin configuring a Jenkins job for this group.",
        reply_markup=reply_markup
    )

def build_keyboard(items: list[str], callback_prefix: str, item_type: str) -> InlineKeyboardMarkup:
    """Tạo bàn phím inline với icon và callback data có prefix."""
    icons = {"folder": "🗂️", "job": "🔨"}
    prefix_icon = icons.get(item_type, "")
    
    keyboard = [
        [InlineKeyboardButton(f"{prefix_icon} {item}", callback_data=f"{callback_prefix}:{item}")]
        for item in items
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"{callback_prefix}:cancel")])
    return InlineKeyboardMarkup(keyboard)

async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bắt đầu cuộc hội thoại setup sau khi nhấn nút."""
    query = update.callback_query
    if not query or not query.message:
        return ConversationHandler.END
        
    await query.answer()

    user = query.from_user
    chat = query.message.chat
    logger.info(f"Starting setup for {user.first_name} (ID: {user.id}) in chat {chat.title} (ID: {chat.id})")
    
    user_id = user.id
    if chat.type == "private":
        await query.edit_message_text("This command only works in a group chat.")
        return ConversationHandler.END

    if not database.is_user_logged_in(user_id):
        await query.edit_message_text("You must /login in a private chat with me first.")
        return ConversationHandler.END
    
    context.user_data['setup_user_id'] = user_id
    # Sửa tin nhắn prompt ban đầu thành tin nhắn loading
    await query.edit_message_text("🔍 Loading your projects...")

    creds = database.get_user_credentials(user_id)
    if not creds:
        await query.edit_message_text("Could not find your credentials. Please /login again.")
        return ConversationHandler.END

    try:
        # Sửa lỗi: Sử dụng key 'jenkins_userid' đã được chuẩn hóa
        server = jenkins.Jenkins(creds['jenkins_url'], username=creds['jenkins_userid'], password=creds['jenkins_token'])
        jobs = server.get_jobs(folder_depth=0)
        folders = [job['name'] for job in jobs if 'folder' in job.get('_class', '').lower()]
        
        if not folders:
            await query.edit_message_text("❌ No project folders found.")
            return ConversationHandler.END
            
        keyboard = build_keyboard(folders, 'setup_folder', "folder")
        await query.edit_message_text("🗂️ Please select your project folder:", reply_markup=keyboard)
        
        # Lưu metadata cho timeout handler
        TimeoutConversationHandler.set_timeout_metadata(
            context, chat.id, query.message.message_id, "setup"
        )
        
        return SELECT_FOLDER
    except Exception as e:
        logger.error(f"Error getting folders: {e}")
        await query.edit_message_text("❌ An error occurred while fetching projects.")
        return ConversationHandler.END

async def select_folder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý lựa chọn thư mục."""
    query = update.callback_query
    if not query or not query.message or not context.user_data:
        return SELECT_FOLDER
    await query.answer()
    
    user_id = query.from_user.id
    if user_id != context.user_data.get('setup_user_id'):
        await query.answer("You are not the one who initiated this command.", show_alert=True)
        return SELECT_FOLDER

    folder_name_data = query.data
    if not folder_name_data:
        return SELECT_FOLDER
    folder_name = folder_name_data.split(':')[1]
    context.user_data['selected_folder'] = folder_name

    creds = database.get_user_credentials(user_id)
    try:
        # Sửa lỗi: Sử dụng key 'jenkins_userid' đã được chuẩn hóa
        server = jenkins.Jenkins(creds['jenkins_url'], username=creds['jenkins_userid'], password=creds['jenkins_token'])
        folder_info = server.get_job_info(folder_name)
        jobs = [job['name'] for job in folder_info.get('jobs', [])]

        if not jobs:
            await query.edit_message_text(f"❌ No jobs found in folder '{folder_name}'.")
            return ConversationHandler.END

        keyboard = build_keyboard(jobs, 'setup_job', "job")
        await query.edit_message_text(f"🗂️ Folder '{folder_name}' selected.\n🔨 Please select a build job:", reply_markup=keyboard)
        return SELECT_JOB_IN_FOLDER
    except Exception as e:
        logger.error(f"Error getting jobs in folder '{folder_name}': {e}")
        await query.edit_message_text("❌ Error accessing folder.")
        return ConversationHandler.END

async def select_job_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý lựa chọn job và hoàn tất setup."""
    query = update.callback_query
    if not query or not query.message or not context.user_data:
        return SELECT_JOB_IN_FOLDER
    await query.answer()
    
    user_id = query.from_user.id
    if user_id != context.user_data.get('setup_user_id'):
        await query.answer("You are not the one who initiated this command.", show_alert=True)
        return SELECT_JOB_IN_FOLDER

    selected_job_data = query.data
    if not selected_job_data:
        return SELECT_JOB_IN_FOLDER
    selected_job = selected_job_data.split(':')[1]
    selected_folder = context.user_data.get('selected_folder')
    if not selected_folder:
        # Xử lý trường hợp không tìm thấy folder
        await query.edit_message_text("Error: Project folder not found in session. Please start over.")
        context.user_data.clear()
        return ConversationHandler.END

    job_path = f"{selected_folder}/{selected_job}"

    try:
        database.save_group_config(query.message.chat.id, job_path, user_id)
        # Sử dụng hàm escape mới
        folder_md = escape_markdown_v2(selected_folder)
        job_md = escape_markdown_v2(selected_job)
        job_path_md = escape_markdown_v2(job_path)
        
        message = (
            f"✅ *Setup Complete\!*\n\n"
            f"🗂️ *Project:* `{folder_md}`\n"
            f"🔨 *Job:* `{job_md}`\n\n"
            f"──────────────\n"
            f"🔗 Group linked to `{job_path_md}`\n"
            f"🚀 Ready to use /build command\!"
        )
        await query.edit_message_text(message, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error saving group config: {e}")
        await query.edit_message_text("❌ An error occurred during setup.")
    
    # Xóa timeout metadata khi hoàn thành thành công
    TimeoutConversationHandler.clear_timeout_metadata(context)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_setup_initial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hủy cuộc hội thoại setup ở bước đầu tiên."""
    query = update.callback_query
    if not query:
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text("Setup process canceled.")
    TimeoutConversationHandler.clear_timeout_metadata(context)
    return ConversationHandler.END

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hủy cuộc hội thoại setup."""
    query = update.callback_query
    if not query:
        return ConversationHandler.END

    await query.answer()
    # Thêm kiểm tra cho context.user_data
    if context.user_data and query.from_user.id == context.user_data.get('setup_user_id'):
        await query.edit_message_text("Setup process canceled.")
        TimeoutConversationHandler.clear_timeout_metadata(context)
        context.user_data.clear()
    else:
        await query.answer("You are not the one who initiated this command.", show_alert=True)
    return ConversationHandler.END
