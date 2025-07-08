import logging
from telegram import Bot
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def on_conversation_timeout(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Xử lý khi conversation timeout xảy ra.
    Cập nhật tin nhắn thành thông báo timeout và xóa keyboard.
    """
    try:
        # Lấy thông tin từ context
        chat_id = context.chat_data.get('chat_id') if context.chat_data else None
        message_id = context.chat_data.get('message_id') if context.chat_data else None
        conversation_type = context.chat_data.get('conversation_type', 'conversation') if context.chat_data else 'conversation'
        
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
            
        # Dọn dẹp chat_data
        if context.chat_data:
            context.chat_data.clear()
            
    except Exception as e:
        logger.error(f"Error in timeout handler: {e}", exc_info=True)


class TimeoutConversationHandler:
    """Helper class để set up timeout metadata cho conversations."""
    
    @staticmethod
    def set_timeout_metadata(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, conversation_type: str):
        """Lưu metadata cần thiết để xử lý timeout."""
        if not context.chat_data:
            context.chat_data = {}
        context.chat_data['chat_id'] = chat_id
        context.chat_data['message_id'] = message_id 
        context.chat_data['conversation_type'] = conversation_type
        
    @staticmethod
    def clear_timeout_metadata(context: ContextTypes.DEFAULT_TYPE):
        """Xóa metadata timeout khi conversation kết thúc thành công."""
        if context.chat_data:
            context.chat_data.pop('chat_id', None)
            context.chat_data.pop('message_id', None)
            context.chat_data.pop('conversation_type', None) 