# handlers/build.py
import logging
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import jenkins

import database
import security
import config

logger = logging.getLogger(__name__)

def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram's MarkdownV2 parse mode."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f"\\{char}" if char in escape_chars else char for char in text)

# Định nghĩa các trạng thái mới cho quy trình build tuần tự
SELECT_BRANCH, SELECT_TARGET = range(2)


async def build_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gửi tin nhắn với nút bấm để bắt đầu cuộc hội thoại build."""
    if not update.message:
        return

    if update.message.chat.type == "private":
        await update.message.reply_text("This command only works in a group chat.")
        return

    group_config = database.get_group_config(update.message.chat.id)
    if not group_config:
        await update.message.reply_text("This group is not set up. Please use /setup first.")
        return

    keyboard = [[InlineKeyboardButton("🚀 Start Build", callback_data="start_build")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Click the button to begin the build process.",
        reply_markup=reply_markup
    )

def _build_options_keyboard(items: list, item_type: str, back_callback: str = None) -> InlineKeyboardMarkup:
    """Tạo bàn phím inline cho các lựa chọn build (branch, target)."""
    icons = {"branch": "🔀", "target": "🎯"}
    icon = icons.get(item_type, "")
    
    keyboard = [
        # Sử dụng f-string để tạo callback_data duy nhất
        [InlineKeyboardButton(f"{icon} {item}", callback_data=f"build_select_{item_type}:{item}")]
        for item in items
    ]
    
    control_row = []
    if back_callback:
        control_row.append(InlineKeyboardButton("⬅️ Back", callback_data=back_callback))
    control_row.append(InlineKeyboardButton("❌ Cancel", callback_data="build_cancel"))
    keyboard.append(control_row)
    
    return InlineKeyboardMarkup(keyboard)


async def build_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bắt đầu cuộc hội thoại build: lấy tham số và hỏi branch."""
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return ConversationHandler.END
    await query.answer()
    
    user = query.from_user
    chat = query.message.chat
    context.user_data['owner_id'] = user.id

    group_config = database.get_group_config(chat.id)
    if not group_config:
        await query.edit_message_text("This group is not set up. Please use /setup first.")
        return ConversationHandler.END

    job_name = group_config[0]
    context.user_data['job_name'] = job_name
    
    await query.edit_message_text(f"🔍 Loading parameters for `{escape_markdown_v2(job_name)}`\\.\\.\\.", parse_mode='MarkdownV2')

    user_creds = database.get_user_credentials(user.id)
    if not user_creds:
        await query.message.reply_html(f"You ({user.mention_html()}) need to /login first.")
        await query.delete_message()
        return ConversationHandler.END

    try:
        server = jenkins.Jenkins(user_creds['jenkins_url'], username=user_creds['jenkins_userid'], password=user_creds['jenkins_token'])
        job_info = server.get_job_info(job_name, depth=2)
        
        param_defs = {}
        for prop in job_info.get('property', []):
            if 'parameterDefinitions' in prop:
                for param in prop['parameterDefinitions']:
                    param_defs[param['name']] = {'choices': param.get('choices', [])}
        
        context.user_data['job_params'] = param_defs
        branches = param_defs.get('GIT_BRANCH', {}).get('choices', [])
        
        if not branches:
            await query.edit_message_text("❌ Could not find any GIT_BRANCH parameter for this job.")
            return ConversationHandler.END

        keyboard = _build_options_keyboard(branches, 'branch')
        await query.edit_message_text("🔀 Please select a branch to build:", reply_markup=keyboard)
        
        return SELECT_BRANCH

    except Exception as e:
        logger.error(f"Error starting build: {e}")
        await query.edit_message_text("❌ An error occurred while fetching job info from Jenkins.")
        return ConversationHandler.END

async def select_branch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý việc chọn branch và hiển thị các build target."""
    query = update.callback_query
    if not query or not query.message or not context.user_data or not query.from_user:
        return ConversationHandler.END
    await query.answer()

    if query.from_user.id != context.user_data.get('owner_id'):
        await query.answer("You are not the one who initiated this command.", show_alert=True)
        return SELECT_BRANCH
    
    selected_branch = query.data.split(':', 1)[1]
    context.user_data['selected_branch'] = selected_branch

    job_params = context.user_data.get('job_params', {})
    targets = job_params.get('BUILD_TARGET', {}).get('choices', [])

    if not targets:
        await query.edit_message_text("❌ Could not find any BUILD_TARGET parameter for this job.")
        return ConversationHandler.END
        
    keyboard = _build_options_keyboard(targets, 'target', back_callback="build_back_to_branch")
    msg = f"🔀 Branch: `{escape_markdown_v2(selected_branch)}`\n\n🎯 Please select a build target:"
    await query.edit_message_text(msg, reply_markup=keyboard, parse_mode='MarkdownV2')
    
    return SELECT_TARGET

async def select_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý việc chọn target, trigger build hoặc quay lại."""
    query = update.callback_query
    if not query or not query.message or not context.user_data or not query.from_user:
        return ConversationHandler.END
    await query.answer()

    if query.from_user.id != context.user_data.get('owner_id'):
        await query.answer("You are not the one who initiated this command.", show_alert=True)
        return SELECT_TARGET
        
    # Xử lý nút "Back"
    if query.data == "build_back_to_branch":
        job_params = context.user_data.get('job_params', {})
        branches = job_params.get('GIT_BRANCH', {}).get('choices', [])
        keyboard = _build_options_keyboard(branches, 'branch')
        await query.edit_message_text("🔀 Please select a branch to build:", reply_markup=keyboard)
        return SELECT_BRANCH

    # Xử lý chọn target và trigger build
    selected_target = query.data.split(':', 1)[1]
    job_name = context.user_data['job_name']
    selected_branch = context.user_data['selected_branch']
    owner_id = context.user_data['owner_id']
    user_creds = database.get_user_credentials(owner_id)

    params = {
        'GIT_BRANCH': selected_branch,
        'BUILD_TARGET': selected_target,
        'BUILD_REQUEST_ID': str(uuid.uuid4()) # Sửa tên tham số cho đúng
    }
    
    try:
        server = jenkins.Jenkins(user_creds['jenkins_url'], username=user_creds['jenkins_userid'], password=user_creds['jenkins_token'])
        server.build_job(job_name, parameters=params)
        
        database.save_build_request(
            params['BUILD_REQUEST_ID'], # Sử dụng đúng key
            job_name, 
            query.message.chat.id, 
            owner_id,
            selected_target # Thêm lại tham số build_target
        )
        
        job_name_md = escape_markdown_v2(job_name)
        branch_md = escape_markdown_v2(selected_branch)
        target_md = escape_markdown_v2(selected_target)
        
        message = (
            f"✅ *Build Triggered\!*\n\n"
            f"🔨 *Job:* `{job_name_md}`\n"
            f"🔀 *Branch:* `{branch_md}`\n"
            f"🎯 *Target:* `{target_md}`\n\n"
            f"I will notify you when it's complete\\."
        )
        await query.edit_message_text(message, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error starting build: {e}")
        await query.edit_message_text("❌ Failed to start the build on Jenkins.")
        
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_build(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hủy cuộc hội thoại build."""
    query = update.callback_query
    if not query or not context.user_data:
        return ConversationHandler.END
    await query.answer()
    
    if query.from_user.id == context.user_data.get('owner_id'):
        await query.edit_message_text("Build process canceled.")
        context.user_data.clear()
        return ConversationHandler.END
    else:
        await query.answer("You are not the one who initiated this command.", show_alert=True)
        # Không kết thúc cuộc hội thoại để người dùng ban đầu có thể tiếp tục
        # Xác định trạng thái hiện tại để quay về cho đúng
        if 'selected_branch' in context.user_data:
            return SELECT_TARGET
        return SELECT_BRANCH
