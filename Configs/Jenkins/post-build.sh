#!/bin/bash

# =================================================================
# Jenkins Unified Post-Build Shell Script (Sử dụng BUILD_RESULT)
# =================================================================
#
# Script này chạy cho TẤT CẢ các kết quả build.
# Nó sử dụng biến môi trường tiêu chuẩn $BUILD_RESULT của Jenkins
# để lấy trạng thái build (SUCCESS, FAILURE, etc.)
#

# --- CẤU HÌNH ---
WEBHOOK_URL="https://webhook.thelegends.io.vn/webhook"

# --- LẤY THÔNG TIN TỪ JENKINS ---
# Lấy kết quả từ biến môi trường tiêu chuẩn của Jenkins
# Chuyển đổi sang chữ hoa để đảm bảo tính nhất quán
CURRENT_BUILD_STATUS=$(echo "$BUILD_RESULT" | tr '[:lower:]' '[:upper:]')

JOB_NAME="$JOB_NAME"
BUILD_NUMBER="$BUILD_NUMBER"
BUILD_TARGET="$BUILD_TARGET"
BUILD_REQUEST_ID="$BUILD_REQUEST_ID"

# --- KIỂM TRA THAM SỐ BUILD_REQUEST_ID ---
if [ -z "$BUILD_REQUEST_ID" ]; then
    echo "LỖI: Biến BUILD_REQUEST_ID không được cung cấp. Bỏ qua việc gửi webhook."
    exit 0
fi

echo "========================================="
echo "Chuẩn bị gửi thông báo (Status: ${CURRENT_BUILD_STATUS})"
echo "========================================="

# --- GỬI REQUEST ĐẾN WEBHOOK ---
HTTP_CODE=$(curl --connect-timeout 10 -s -o /dev/null -w "%{http_code}" \
    "$WEBHOOK_URL?job_name=${JOB_NAME}&build_number=${BUILD_NUMBER}&status=${CURRENT_BUILD_STATUS}&build_target=${BUILD_TARGET}&build_request_id=${BUILD_REQUEST_ID}")

# --- KIỂM TRA KẾT QUẢ ---
echo "Webhook đã trả về mã trạng thái HTTP: $HTTP_CODE"

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "Thông báo ${CURRENT_BUILD_STATUS} đã được gửi thành công."
    exit 0
else
    echo "LỖI: Gửi thông báo ${CURRENT_BUILD_STATUS} thất bại (Mã HTTP: $HTTP_CODE)."
    exit 1
fi