import logging
import re

class HTMLErrorFilter(logging.Filter):
    """Bộ lọc để làm sạch các thông báo lỗi HTML trong log."""
    
    def filter(self, record):
        if record.levelno == logging.ERROR and hasattr(record, 'msg'):
            # Kiểm tra nếu thông báo chứa HTML
            if isinstance(record.msg, str):
                # Loại bỏ các thẻ HTML
                if "<html>" in record.msg.lower():
                    # Rút gọn thông báo HTML
                    html_match = re.search(r'<title>(.*?)</title>', record.msg, re.IGNORECASE)
                    if html_match:
                        # Chỉ hiển thị tiêu đề của trang HTML lỗi
                        record.msg = f"HTML Error: {html_match.group(1)}"
                    else:
                        # Nếu không tìm thấy tiêu đề, hiển thị thông báo chung
                        record.msg = "HTML Error received from API (content hidden)"
                
                # Rút gọn thông báo lỗi quá dài
                if len(record.msg) > 200:
                    record.msg = record.msg[:200] + "... (truncated)"
        return True

# Hàm tiện ích để thêm bộ lọc vào logger
def add_html_filter_to_logger(logger_name=None):
    """
    Thêm HTMLErrorFilter vào logger được chỉ định hoặc root logger.
    
    Args:
        logger_name: Tên của logger cần thêm bộ lọc. Nếu None, sẽ thêm vào root logger.
    """
    if logger_name:
        logger = logging.getLogger(logger_name)
    else:
        logger = logging.getLogger()
    
    logger.addFilter(HTMLErrorFilter())
    return logger 