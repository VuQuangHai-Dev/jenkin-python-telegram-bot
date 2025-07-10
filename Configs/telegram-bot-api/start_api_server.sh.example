#!/bin/bash

# ==============================================================================
# Shell script to run the local Telegram Bot API server on macOS or Linux
# ==============================================================================

# This line ensures that the script runs from the directory where it is located.
# This is important so that it can find the 'telegram-bot-api' executable.
cd "$(dirname "$0")"

# --- CONFIGURATION ---
# 1. Fill in your API ID and API Hash from my.telegram.org.
API_ID="YOUR_API_ID"
API_HASH="YOUR_API_HASH"

# 2. This is the proxy address. For WARP SOCKS5, this is the default.
PROXY="socks5://127.0.0.1:40000"

# 3. This should be the name of the executable file in the same directory.
# After compiling from source, the file is usually just 'telegram-bot-api'.
EXECUTABLE="./build/telegram-bot-api"

# 4. The path to the local proxychains config file.
# Update this path if you move the config file.
PROXY_CONFIG_FILE="./proxychains/telegram-bot-api-proxychains.conf"
# --- END OF CONFIGURATION ---


# Check if the executable exists
if [ ! -f "$EXECUTABLE" ]; then
    echo "ERROR: Executable '$EXECUTABLE' not found in the 'build' directory."
    echo "Please make sure you have compiled the project successfully."
    exit 1
fi

# Check if the local proxy config file exists
if [ ! -f "$PROXY_CONFIG_FILE" ]; then
    echo "ERROR: Proxy config file '$PROXY_CONFIG_FILE' not found."
    echo "Please create it in the same directory as this script."
    exit 1
fi

echo "--- Starting Telegram Bot API server ---"
echo "Executable:          $EXECUTABLE"
echo "API ID:              $API_ID"
echo "Using Proxy Config:  $PROXY_CONFIG_FILE"
echo "----------------------------------------"
echo ""

# Run the server, wrapped by proxychains4 using the specified local config file.
# The --local flag is added to explicitly allow requests from the bot running on the same machine.
proxychains4 -f "$PROXY_CONFIG_FILE" "$EXECUTABLE" --api-id="$API_ID" --api-hash="$API_HASH" --local

echo ""
echo "--- Server has stopped ---" 