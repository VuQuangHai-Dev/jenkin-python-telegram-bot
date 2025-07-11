# handlers package
import logging
from log_filters import add_html_filter_to_logger

# Áp dụng bộ lọc HTML cho tất cả các logger trong module handlers
add_html_filter_to_logger('handlers')
add_html_filter_to_logger('handlers.commands')
add_html_filter_to_logger('handlers.setup')
add_html_filter_to_logger('handlers.build')
