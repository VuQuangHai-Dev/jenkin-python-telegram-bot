import logging
import re

class HTMLErrorFilter(logging.Filter):
    """Bộ lọc để làm sạch các thông báo lỗi HTML trong log."""
    
    def filter(self, record):
        if hasattr(record, 'msg'):
            # Kiểm tra nếu thông báo là chuỗi
            if isinstance(record.msg, str):
                # Kiểm tra các dấu hiệu của HTML
                html_indicators = ["<html>", "</html>", "<body>", "</body>", "<head>", 
                                  "<title>", "<!DOCTYPE", "<meta", "<tr>", "<td>", 
                                  "<table>", "<h1>", "<h2>", "<h3>"]
                
                is_html = any(indicator.lower() in record.msg.lower() for indicator in html_indicators)
                
                if is_html:
                    # Cố gắng trích xuất thông tin hữu ích từ HTML
                    # 1. Thử lấy tiêu đề
                    title_match = re.search(r'<title>(.*?)</title>', record.msg, re.IGNORECASE | re.DOTALL)
                    if title_match:
                        title = title_match.group(1).strip()
                        record.msg = f"HTML Error: {title}"
                    else:
                        # 2. Thử lấy nội dung thẻ h1, h2, h3
                        h_match = re.search(r'<h[1-3][^>]*>(.*?)</h[1-3]>', record.msg, re.IGNORECASE | re.DOTALL)
                        if h_match:
                            heading = h_match.group(1).strip()
                            record.msg = f"HTML Error: {heading}"
                        else:
                            # 3. Thử lấy thông báo lỗi từ thẻ body
                            body_match = re.search(r'<body[^>]*>(.*?)</body>', record.msg, re.IGNORECASE | re.DOTALL)
                            if body_match:
                                # Lấy text từ body và loại bỏ các thẻ HTML
                                body_text = body_match.group(1)
                                body_text = re.sub(r'<[^>]+>', ' ', body_text)
                                body_text = re.sub(r'\s+', ' ', body_text).strip()
                                if len(body_text) > 100:
                                    body_text = body_text[:100] + "..."
                                record.msg = f"HTML Error: {body_text}"
                            else:
                                # 4. Fallback: Hiển thị thông báo chung
                                record.msg = "HTML Error received (content hidden)"
                
                # Kiểm tra các chuỗi lỗi HTTP phổ biến
                http_error_match = re.search(r'HTTP ERROR (\d+)', record.msg, re.IGNORECASE)
                if http_error_match:
                    error_code = http_error_match.group(1)
                    record.msg = f"HTTP Error {error_code} received"
                
                # Rút gọn thông báo lỗi quá dài
                if len(record.msg) > 200:
                    record.msg = record.msg[:200] + "... (truncated)"
                    
            # Nếu thông báo là exception
            elif isinstance(record.msg, Exception):
                # Chuyển đổi exception thành chuỗi và kiểm tra HTML
                msg_str = str(record.msg)
                if "<html>" in msg_str.lower() or "</html>" in msg_str.lower():
                    record.msg = "HTML Error in exception (content hidden)"
                elif len(msg_str) > 200:
                    record.msg = f"{msg_str[:200]}... (truncated)"
        
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
    
    # Kiểm tra xem bộ lọc đã được thêm vào chưa
    filter_exists = any(isinstance(f, HTMLErrorFilter) for f in logger.filters)
    if not filter_exists:
        logger.addFilter(HTMLErrorFilter())
    
    return logger 