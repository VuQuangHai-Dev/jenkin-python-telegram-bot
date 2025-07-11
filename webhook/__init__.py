# webhook package
import logging
from log_filters import add_html_filter_to_logger
from .server import webhook_handler

# Áp dụng bộ lọc HTML cho tất cả các logger trong module webhook
add_html_filter_to_logger('webhook')
add_html_filter_to_logger('webhook.server')

__all__ = ['webhook_handler']
