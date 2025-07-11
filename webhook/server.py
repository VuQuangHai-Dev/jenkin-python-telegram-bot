# webhook/server.py
import logging
from aiohttp import web
import os
import aiohttp
from urllib.parse import urljoin
from log_filters import add_html_filter_to_logger

import database
import security
from telegram.constants import ParseMode
from telegram import InputFile, InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)
add_html_filter_to_logger(__name__)

def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram's MarkdownV2 parse mode."""
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f"\\{char}" if char in escape_chars else char for char in text)

async def webhook_handler(request: web.Request) -> web.Response:
    """Xử lý các request đến từ webhook của Jenkins."""
    app = request.app['bot_instance']['app']
    bot = app.bot
    try:
        data = request.query
        job_name = data.get('job_name')
        build_number_str = data.get('build_number')
        status = data.get('status')
        build_target = data.get('build_target')
        build_request_id = data.get('build_request_id')

        if not all([job_name, build_number_str, status]):
            logger.warning(f"Webhook received with missing data: {data}")
            return web.Response(text="Missing data", status=400)
        
        # Chạy tác vụ nền để không block Jenkins
        app.create_task(
            process_build_notification(
                bot=bot,
                job_name=job_name,
                build_number_str=build_number_str,
                status=status,
                build_target=build_target,
                build_request_id=build_request_id
            )
        )
        
        return web.Response(text="OK, job is being processed.", status=200)

    except Exception as e:
        logger.error(f"Error processing webhook initial request: {e}", exc_info=True)
        return web.Response(text=f"Internal Server Error: {str(e)}", status=500)

async def process_build_notification(bot, job_name, build_number_str, status, build_target, build_request_id):
    """Tác vụ chạy nền để xử lý thông báo và gửi file."""
    try:
        build_number = int(build_number_str)
        logger.info(f"BACKGROUND TASK: Processing job={job_name}, build_number={build_number}, status={status}")

        build_request = database.get_build_request(build_request_id) if build_request_id else None
        if not build_request:
            logger.warning(f"Build request ID {build_request_id} not found, falling back to latest.")
            build_request = database.get_latest_build_request(job_name)

        if not build_request:
            logger.warning(f"No build request found for job: {job_name}, build: {build_number}")
            return
        
        group_id = build_request['telegram_group_id']
        user_id = build_request['requested_by_user_id']
        
        creds = database.get_user_credentials(user_id)
        if not creds:
            await bot.send_message(group_id, f"System Error: Could not find credentials for user {user_id}.")
            return

        jenkins_url = creds['jenkins_url']
        job_url_path = '/'.join([f"job/{part}" for part in job_name.split('/')])
        
        # Escape các biến trước khi sử dụng trong MarkdownV2
        job_name_md = escape_markdown_v2(job_name)
        build_target_md = escape_markdown_v2(build_target or 'Unknown')
        status_md = escape_markdown_v2(status)
        
        # --- Xây dựng link và tin nhắn cho cả hai trường hợp ---
        links_text = []

        # 1. Thêm link Unity Log nếu có build_target
        if build_target:
            unity_log_url = urljoin(jenkins_url, f"{job_url_path}/ws/unity_build_{build_target}.log").replace(')', r'\)')
            links_text.append(f"📜 [View Unity Build Log]({unity_log_url})")

        # 2. Luôn thêm link Console Log
        console_log_url = urljoin(jenkins_url, f"{job_url_path}/{build_number}/console").replace(')', r'\)')
        links_text.append(f"📝 [View Console Log]({console_log_url})")

        links_md = chr(10).join(links_text)
        
        if status.upper() == 'SUCCESS':
            # --- Gửi tin nhắn thành công ---
            message_text = (
                f"✅ *Build Succeeded\!*\n\n"
                f"*Job:* `{job_name_md}`\n"
                f"*Build:* `#{build_number}`\n"
                f"*Target:* `{build_target_md}`\n\n"
                f"{links_md}"
            )
            
            sent_message = await bot.send_message(
                group_id, 
                message_text, 
                parse_mode=ParseMode.MARKDOWN_V2, 
                disable_web_page_preview=True
            )

            # --- Gửi tệp build bằng cách đọc file cục bộ ---
            async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(creds['jenkins_userid'], creds['jenkins_token'])) as session:
                local_build_file_path = None
                
                # 1. Lấy đường dẫn file cục bộ từ properties trong workspace của Jenkins
                # Phải truy cập vào workspace (ws) thay vì artifact và không có build number trong URL
                props_url = urljoin(jenkins_url, f"{job_url_path}/ws/build_info.properties")
                logger.info(f"Attempting to get build properties from: {props_url}")
                try:
                    async with session.get(props_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            text = await response.text()
                            properties = {k.strip(): v.strip() for k, v in (line.split('=', 1) for line in text.splitlines() if '=' in line)}
                            local_build_file_path = properties.get('LATEST_BUILD_FILE')
                            logger.info(f"Found local build file path from properties: {local_build_file_path}")
                        else:
                            logger.warning(f"Could not fetch build_info.properties from workspace. Status: {response.status}")
                except Exception as e:
                    logger.error(f"Could not get build file path from properties: {e}")

                # 2. Nếu có đường dẫn, đọc file từ máy chủ và gửi
                if local_build_file_path and os.path.exists(local_build_file_path):
                    # Sửa tin nhắn đã gửi để thêm trạng thái Uploading
                    try:
                        uploading_message = message_text + "\n\nUploading file\\.\\.\\."
                        await bot.edit_message_text(
                            text=uploading_message,
                            chat_id=group_id,
                            message_id=sent_message.message_id,
                            parse_mode=ParseMode.MARKDOWN_V2,
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        logger.warning(f"Could not edit message to add 'Uploading...' text: {e}")

                    # Sửa tên file để chứa build_target
                    original_file_name = os.path.basename(local_build_file_path)
                    name, ext = os.path.splitext(original_file_name)
                    new_file_name = f"{name}_{build_target}{ext}" if build_target else original_file_name

                    try:
                        with open(local_build_file_path, 'rb') as f:
                            await bot.send_document(
                                chat_id=group_id,
                                document=f,
                                filename=new_file_name,
                                read_timeout=600,
                                write_timeout=600,
                                connect_timeout=30
                            )
                        logger.info(f"Successfully sent file from local path: {local_build_file_path}")
                    except Exception as e:
                        error_msg = f"⚠️ An error occurred while sending the build file: `{escape_markdown_v2(str(e))}`"
                        logger.error(f"Error sending local artifact for job {job_name} build {build_number}: {e}", exc_info=True)
                        await bot.send_message(group_id, error_msg, parse_mode=ParseMode.MARKDOWN_V2)

                elif local_build_file_path:
                    # File path was in properties but not found on disk
                    error_msg = f"⚠️ Error: Build file specified but not found at path: `{escape_markdown_v2(local_build_file_path)}`\\. Please check permissions and path accessibility for the bot\\."
                    logger.error(f"File path from properties not found on disk: {local_build_file_path}")
                    await bot.send_message(group_id, error_msg, parse_mode=ParseMode.MARKDOWN_V2)
                else:
                    # LATEST_BUILD_FILE was not in properties file
                    logger.info(f"No 'LATEST_BUILD_FILE' property found for job {job_name}, build {build_number}. Skipping file sending.")
                    await bot.send_message(group_id, "Build successful, but no artifact file was specified to be sent\\.", parse_mode=ParseMode.MARKDOWN_V2)

        else:
            # --- Gửi tin nhắn thất bại ---
            message_text = (
                f"❌ *Build Failed\!*\n\n"
                f"*Job:* `{job_name_md}`\n"
                f"*Build:* `#{build_number}`\n"
                f"*Status:* `{status_md}`\n\n"
                f"{links_md}"
            )
            await bot.send_message(
                group_id, 
                message_text, 
                parse_mode=ParseMode.MARKDOWN_V2, 
                disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"BACKGROUND TASK: Failed for job {job_name}: {e}", exc_info=True)
        # Attempt to notify group about the error
        try:
            if 'group_id' in locals():
                await bot.send_message(locals()['group_id'], f"An internal error occurred while processing the build result.")
        except Exception as notify_e:
            logger.error(f"Failed to even notify the group about the error: {notify_e}")
