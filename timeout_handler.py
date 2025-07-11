import logging
import time
from telegram import Bot
from telegram.ext import ContextTypes
from log_filters import add_html_filter_to_logger

logger = logging.getLogger(__name__)
add_html_filter_to_logger(__name__)

# Dictionary để lưu các tin nhắn cần cập nhật khi timeout
# Key: user_id, Value: (chat_id, message_id, timeout_time, conversation_type)
timeout_messages = {}

# Biến toàn cục để lưu trữ job hiện tại
_current_timeout_job = None
_job_queue = None
_callback_function = None  # Lưu trữ callback function

def register_timeout_job(job_queue, callback_function, interval=30):
    """
    Đăng ký job kiểm tra timeout nếu chưa tồn tại.
    
    Args:
        job_queue: JobQueue instance
        callback_function: Hàm callback để kiểm tra timeout
        interval: Khoảng thời gian giữa các lần chạy (giây)
    """
    global _current_timeout_job, _job_queue, _callback_function
    
    # Lưu job_queue và callback_function để có thể tạo job mới sau này
    _job_queue = job_queue
    _callback_function = callback_function
    
    # Chỉ tạo job mới nếu không có job nào đang chạy
    if _current_timeout_job is None:
        _current_timeout_job = job_queue.run_repeating(
            callback_function, 
            interval=interval, 
            first=interval
        )
        logger.info(f"Timeout checker job started with {interval} second interval")

def remove_timeout_job():
    """
    Hủy job timeout hiện tại nếu không còn cần thiết.
    """
    global _current_timeout_job
    
    if _current_timeout_job is not None:
        _current_timeout_job.schedule_removal()
        _current_timeout_job = None
        logger.info("Timeout checker job stopped")

def start_timeout_job_if_needed():
    """
    Bắt đầu job timeout nếu có tin nhắn cần kiểm tra và không có job nào đang chạy.
    """
    global _current_timeout_job, _job_queue, _callback_function
    
    if timeout_messages and _current_timeout_job is None and _job_queue is not None and _callback_function is not None:
        _current_timeout_job = _job_queue.run_repeating(
            _callback_function, 
            interval=30, 
            first=30
        )
        logger.info("Timeout checker job restarted with %d messages to check", len(timeout_messages))

async def on_conversation_timeout(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Xử lý khi conversation timeout xảy ra.
    Cập nhật tin nhắn thành thông báo timeout và xóa keyboard.
    """
    try:
        # Lấy thông tin từ context
        chat_id = context.user_data.get('timeout_chat_id') if context.user_data else None
        message_id = context.user_data.get('timeout_message_id') if context.user_data else None
        conversation_type = context.user_data.get('timeout_conversation_type', 'conversation') if context.user_data else 'conversation'
        
        # Nếu có message_id, update tin nhắn hiện tại
        if chat_id and message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"⏰ {conversation_type.title()} timed out due to inactivity.\n\nPlease start over by using the command again.",
                    reply_markup=None  # Xóa keyboard
                )
                logger.info(f"Updated timeout message for {conversation_type} in chat {chat_id}, message {message_id}")
            except Exception as edit_error:
                logger.warning(f"Could not edit timeout message: {edit_error}")
                # Fallback: gửi tin nhắn mới
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏰ {conversation_type.title()} timed out due to inactivity. Please start over."
                )
        
        # Dọn dẹp user_data
        if context.user_data:
            context.user_data.clear()
            
    except Exception as e:
        logger.error(f"Error in timeout handler: {e}", exc_info=True)


class TimeoutConversationHandler:
    """Helper class để set up timeout metadata cho conversations."""
    
    @staticmethod
    def set_timeout_metadata(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, conversation_type: str):
        """Lưu metadata cần thiết để xử lý timeout."""
        # Lưu vào user_data
        if context.user_data is None:
            logger.warning("user_data is None, cannot store timeout metadata")
            return
            
        context.user_data['timeout_chat_id'] = chat_id
        context.user_data['timeout_message_id'] = message_id 
        context.user_data['timeout_conversation_type'] = conversation_type
        
        # Thêm vào timeout_messages global
        user_id = context.user_data.get('setup_user_id') or context.user_data.get('owner_id')
        if user_id:
            # Tính thời gian timeout (5 phút = 300 giây)
            timeout_time = time.time() + 300
            # Tạo key duy nhất cho mỗi tin nhắn (chat_id + message_id)
            message_key = f"{chat_id}:{message_id}"
            # Lưu thông tin với key là message_key
            timeout_messages[message_key] = (chat_id, message_id, timeout_time, conversation_type)
            logger.info(f"Added timeout message for user {user_id}, chat {chat_id}, message {message_id}")
            
            # Bắt đầu job timeout nếu cần
            start_timeout_job_if_needed()
        
    @staticmethod
    def clear_timeout_metadata(context: ContextTypes.DEFAULT_TYPE):
        """Xóa metadata timeout khi conversation kết thúc thành công."""
        if context.user_data:
            # Lấy thông tin chat_id và message_id
            chat_id = context.user_data.get('timeout_chat_id')
            message_id = context.user_data.get('timeout_message_id')
            
            # Xóa khỏi timeout_messages global nếu có
            if chat_id and message_id:
                message_key = f"{chat_id}:{message_id}"
                if message_key in timeout_messages:
                    timeout_messages.pop(message_key, None)
                    logger.info(f"Removed timeout message for chat {chat_id}, message {message_id}")
                
            # Xóa khỏi user_data
            context.user_data.pop('timeout_chat_id', None)
            context.user_data.pop('timeout_message_id', None)
            context.user_data.pop('timeout_conversation_type', None) 