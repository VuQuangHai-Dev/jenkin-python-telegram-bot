import logging
import asyncio
import time
from aiohttp import web

from telegram import Update
from telegram.ext import Application
from telegram.constants import ParseMode

import config
import database
from webhook.server import webhook_handler
from handlers import commands, setup, build
from telegram.ext import CommandHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, JobQueue
from timeout_handler import timeout_messages, register_timeout_job, remove_timeout_job

# Cấu hình logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("JenkinsBot")

async def main() -> None:
    """Hàm chính, khởi động bot, các handler, và web server."""
    database.init_db()

    # Thêm JobQueue để hỗ trợ conversation_timeout
    job_queue = JobQueue()
    
    # Hàm xử lý timeout - chạy định kỳ để kiểm tra và cập nhật tin nhắn timeout
    async def check_timeouts(context):
        current_time = time.time()
        
        # Kiểm tra các tin nhắn đã lưu
        to_remove = []
        if not timeout_messages:
            # Không có tin nhắn nào cần kiểm tra, hủy job
            remove_timeout_job()
            return
            
        logger.info(f"Checking {len(timeout_messages)} timeout messages")
        
        for key, data in timeout_messages.items():
            chat_id, message_id, timeout_time, conv_type = data
            
            # Nếu đã quá thời gian timeout
            if current_time > timeout_time:
                try:
                    # Cập nhật tin nhắn
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"⏰ {conv_type.title()} timed out due to inactivity.\n\nPlease start over by using the command again.",
                        reply_markup=None
                    )
                    logger.info(f"Updated timeout message for {conv_type} in chat {chat_id}")
                    to_remove.append(key)
                except Exception as e:
                    logger.error(f"Error updating timeout message: {e}")
                    to_remove.append(key)
        
        # Xóa các tin nhắn đã xử lý
        for key in to_remove:
            timeout_messages.pop(key, None)
            
        # Nếu không còn tin nhắn nào cần kiểm tra, hủy job
        if not timeout_messages:
            remove_timeout_job()

    # Sử dụng context-based-callbacks
    application = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .base_url(f"{config.LOCAL_BOT_API_URL}/bot")
        .base_file_url(f"{config.LOCAL_BOT_API_URL}/file/bot")
        .job_queue(job_queue)
        .build()
    )
    
    # Đăng ký hàm check_timeouts với job_queue
    register_timeout_job(job_queue, check_timeouts)

    # --- Đăng ký các handlers ---

    # Các lệnh đơn giản
    application.add_handler(CommandHandler("start", commands.start_handler))
    application.add_handler(CommandHandler("help", commands.help_handler))
    application.add_handler(CommandHandler("logout", commands.logout_handler))
    # Các lệnh prompt cho conversation
    application.add_handler(CommandHandler("setup", setup.setup_prompt))
    application.add_handler(CommandHandler("build", build.build_prompt))
    
    # Handlers cho nút Cancel ban đầu (trước khi conversation bắt đầu)
    application.add_handler(CallbackQueryHandler(setup.cancel_setup_initial, pattern='^cancel_setup_initial$'))
    application.add_handler(CallbackQueryHandler(build.cancel_build_initial, pattern='^cancel_build_initial$'))

    # Conversation Handler cho /login
    login_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('login', commands.login_start)],
        states={
            commands.GET_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, commands.get_url)],
            commands.GET_USERID: [MessageHandler(filters.TEXT & ~filters.COMMAND, commands.get_userid)],
            commands.GET_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, commands.get_token)],
        },
        fallbacks=[CommandHandler('cancel', commands.cancel_login)],
    )
    application.add_handler(login_conv_handler)

    # Conversation Handler cho /setup
    setup_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(setup.setup_start, pattern='^start_setup$')],
        states={
            # Sử dụng pattern đơn giản hơn để tránh lỗi
            setup.SELECT_FOLDER: [CallbackQueryHandler(setup.select_folder_callback, pattern='^setup_folder:.*')],
            setup.SELECT_JOB_IN_FOLDER: [CallbackQueryHandler(setup.select_job_callback, pattern='^setup_job:.*')],
        },
        fallbacks=[
            CallbackQueryHandler(setup.cancel_setup_initial, pattern='^cancel_setup_initial$'),
            CallbackQueryHandler(setup.cancel_setup, pattern='^setup_folder:cancel$|^setup_job:cancel$')
        ],
        conversation_timeout=300,
        per_message=True,
    )
    application.add_handler(setup_conv_handler)

    # Conversation Handler cho /build
    build_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(build.build_start, pattern='^start_build$')],
        states={
            build.SELECT_BRANCH: [
                CallbackQueryHandler(build.select_branch, pattern='^build_select_branch:.*')
            ],
            build.SELECT_TARGET: [
                CallbackQueryHandler(build.select_target, pattern='^build_select_target:.*|^build_back_to_branch$')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(build.cancel_build_initial, pattern='^cancel_build_initial$'),
            CallbackQueryHandler(build.cancel_build, pattern='^build_cancel$|^build_select_branch:cancel$|^build_select_target:cancel$')
        ],
        conversation_timeout=300,
        per_message=True,
    )
    application.add_handler(build_conv_handler)


    # Cấu hình Web Server cho webhook
    webhook_app = web.Application()
    # Tạo một dict chứa các instance cần thiết để handler có thể truy cập
    webhook_app['bot_instance'] = {
        'app': application
    }
    webhook_app.add_routes([web.get('/webhook', webhook_handler)])
    
    runner = web.AppRunner(webhook_app)
    
    # --- Chạy đồng thời Bot Polling và Web Server ---
    async with application:
        await application.initialize()
        await application.start()
        # Bắt đầu lắng nghe tin nhắn từ Telegram
        if application.updater:
            await application.updater.start_polling()

        # Khởi động web server
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8088)
        await site.start()

        # --- Log thông tin khởi động ---
        bot_info = await application.bot.get_me()
        if bot_info:
            logger.info(f"👤 Connected as: {bot_info.first_name} (@{bot_info.username}) (ID: {bot_info.id})")
        logger.info("🚀 Bot is running...")
        logger.info(f"👂 Webhook is listening on http://localhost:8088/webhook")
        
        # Giữ cho tiến trình chính sống
        while True:
            await asyncio.sleep(3600)

        # Đoạn code dưới đây sẽ được chạy khi bot tắt (ví dụ: nhấn Ctrl+C)
        logger.info("Stopping bot and webhook server...")
        if application.updater:
            await application.updater.stop()
        await application.stop()
        await runner.cleanup()
        logger.info("Cleanup complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.") 