#!/bin/bash
set -e

# --- CẤU HÌNH TRUNG TÂM ---
# Biến này có thể được ghi đè bởi Jenkins Parameter có tên UNITY_VERSION
export UNITY_VERSION=${UNITY_VERSION:-"2021.3.45f1"}
# Đường dẫn đến Unity Editor, được sử dụng cho cả kích hoạt và build
UNITY_PATH="/Applications/Unity/Hub/Editor/$UNITY_VERSION/Unity.app/Contents/MacOS/Unity"


# --- HÀM KÍCH HOẠT UNITY THÔNG MINH ---
activate_unity() {
    echo "--- Checking Unity License Activation for version $UNITY_VERSION ---"

    # 1. Kiểm tra xem các biến môi trường credentials có tồn tại không
    if [ -z "$UNITY_USERNAME" ] || [ -z "$UNITY_PASSWORD" ]; then
        echo "❌ ERROR: UNITY_USERNAME or UNITY_PASSWORD not set in Jenkins environment."
        echo "Please configure Jenkins credentials binding."
        exit 1
    fi

    # 2. Kiểm tra xem đường dẫn Unity có hợp lệ không
    if [ ! -f "$UNITY_PATH" ]; then
        echo "❌ ERROR: Could not find Unity executable at specified path: $UNITY_PATH"
        echo "Please check if UNITY_VERSION ($UNITY_VERSION) is correct and installed."
        exit 1
    fi
    echo "✅ Using Unity executable at: $UNITY_PATH"


    # 3. Tạo lệnh kích hoạt
    LICENSE_CMD_ARGS=("-quit" "-batchmode" "-nographics" "-username" "$UNITY_USERNAME" "-password" "$UNITY_PASSWORD")
    
    # Thêm serial key nếu có
    if [ -n "$UNITY_SERIAL_KEY" ]; then
        echo "🔑 Unity Pro serial key found, adding to activation command."
        LICENSE_CMD_ARGS+=("-serial" "$UNITY_SERIAL_KEY")
    else
        echo "ℹ️ No Unity Pro serial key found, activating Personal license."
    fi

    # 4. Chạy lệnh kích hoạt một cách "im lặng"
    # Log sẽ được ghi vào một file tạm và chỉ hiển thị nếu có lỗi
    echo "🚀 Attempting to activate Unity license..."
    ACTIVATION_LOG="$WORKSPACE/unity_activation.log"
    
    if "$UNITY_PATH" "${LICENSE_CMD_ARGS[@]}" -logFile "$ACTIVATION_LOG"; then
        echo "🎉 ✅ Unity license activation successful or already active."
        # Có thể xóa log nếu thành công để giữ cho workspace sạch sẽ
        # rm -f "$ACTIVATION_LOG"
    else
        echo "❌ ERROR: Unity license activation failed. See log below."
        echo "==================== UNITY ACTIVATION LOG ===================="
        cat "$ACTIVATION_LOG"
        echo "=============================================================="
        exit 1
    fi
    echo "-------------------------------------------"
    echo ""
}


echo "================== JENKINS UNIVERSAL BUILD SCRIPT START =================="

# --- KÍCH HOẠT UNITY ---
# Gọi hàm kích hoạt ở ngay đầu
activate_unity

# --- JENKINS PARAMETERS (Set in Jenkins Job Configuration) ---
# BUILD_TARGET: "android-apk", "android-apk-dev", "android-aab", "ios-ipa", "ios-ipa-dev", "ios-appstore"
# BUILD_PREFIX: "d10b" (project name)
# GIT_BRANCH: "master", "dev" (git branch to build from)
# CLEANUP: Automatic cleanup keeps builds for 7 days (hardcoded) 

# --- BUILD TIMING FUNCTION ---
show_build_duration() {
    local end_time=$(date +%s)
    local duration=$((end_time - BUILD_START_TIME))
    local hours=$((duration / 3600))
    local minutes=$(((duration % 3600) / 60))
    local seconds=$((duration % 60))
    
    echo ""
    echo "⏱️ ========== BUILD DURATION =========="
    if [ $hours -gt 0 ]; then
        echo "⏰ Total build time: ${hours}h ${minutes}m ${seconds}s (${duration}s)"
    elif [ $minutes -gt 0 ]; then
        echo "⏰ Total build time: ${minutes}m ${seconds}s (${duration}s)"
    else
        echo "⏰ Total build time: ${seconds}s"
    fi
    echo "⏱️ Build started at: $(date -r $BUILD_START_TIME '+%Y-%m-%d %H:%M:%S')"
    echo "🏁 Build finished at: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "======================================="
    echo ""
}

# --- CLEANUP FUNCTION ---
cleanup_old_builds() {
    local cleanup_days=7  # Fixed: Keep builds for 7 days
    local builds_root_dir="$WORKSPACE/Builds"
    
    if [ ! -d "$builds_root_dir" ]; then
        echo "📁 No builds directory found, skipping cleanup"
        return 0
    fi
    
    echo "🧹 ========== CLEANUP OLD BUILDS =========="
    echo "🗂️ Cleanup directory: $builds_root_dir"
    echo "📅 Cleanup threshold: $cleanup_days days"
    echo "⏰ Current time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # Count files before cleanup
    local total_files_before=$(find "$builds_root_dir" -type f \( -name "*.apk" -o -name "*.aab" -o -name "*.ipa" \) | wc -l)
    local total_size_before=$(du -sh "$builds_root_dir" 2>/dev/null | cut -f1 || echo "0B")
    
    echo "📊 BEFORE CLEANUP:"
    echo "   📁 Total build files: $total_files_before"
    echo "   💾 Total size: $total_size_before"
    echo ""
    
    # Find and list files to be deleted
    local files_to_delete=$(find "$builds_root_dir" -type f \( -name "*.apk" -o -name "*.aab" -o -name "*.ipa" \) -mtime +$cleanup_days)
    local files_count=0
    if [ -n "$files_to_delete" ]; then
        files_count=$(echo "$files_to_delete" | grep -c . 2>/dev/null || echo "0")
    fi
    
    if [ "${files_count:-0}" -gt 0 ] && [ -n "$files_to_delete" ]; then
        echo "🗑️  FILES TO DELETE (older than $cleanup_days days):"
        echo "$files_to_delete" | while read -r file; do
            if [ -f "$file" ]; then
                local file_date=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$file" 2>/dev/null || date -r "$file" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "unknown")
                local file_size=$(du -h "$file" 2>/dev/null | cut -f1 || echo "0B")
                echo "   🗂️  $(basename "$file") - $file_size - $file_date"
            fi
        done
        
        echo ""
        echo "🗑️  Deleting $files_count old build files..."
        echo "$files_to_delete" | while read -r file; do
            if [ -f "$file" ]; then
                rm -f "$file"
                echo "   ✅ Deleted: $(basename "$file")"
            fi
        done
        
        # Clean up empty directories
        find "$builds_root_dir" -type d -empty -delete 2>/dev/null || true
        echo "   🧹 Cleaned up empty directories"
    else
        echo "✨ No files older than $cleanup_days days found"
    fi
    
    # Count files after cleanup
    local total_files_after=$(find "$builds_root_dir" -type f \( -name "*.apk" -o -name "*.aab" -o -name "*.ipa" \) | wc -l || echo "0")
    local total_size_after=$(du -sh "$builds_root_dir" 2>/dev/null | cut -f1 || echo "0B")
    local files_deleted=$((total_files_before - total_files_after))
    
    echo ""
    echo "📊 AFTER CLEANUP:"
    echo "   📁 Remaining build files: $total_files_after"
    echo "   💾 Remaining size: $total_size_after"
    echo "   🗑️ Files deleted: $files_deleted"
    echo "==============================================="
    echo ""
}

# --- PARAMETER VALIDATION ---
if [ -z "$BUILD_TARGET" ]; then
    echo "❌ ERROR: BUILD_TARGET parameter is required!"
    echo "Valid values: android-apk, android-apk-dev, android-aab, ios-ipa, ios-ipa-dev, ios-appstore"
    exit 1
fi

if [ -z "$BUILD_PREFIX" ]; then
    echo "❌ ERROR: BUILD_PREFIX parameter is required!"
    echo "Set in Jenkins job parameters"
    exit 1
fi

if [ -z "$GIT_BRANCH" ]; then
    echo "❌ ERROR: GIT_BRANCH parameter is required!"
    echo "Valid values: master, dev"
    exit 1
fi

# --- BUILD CONFIGURATION SETUP ---
case "$BUILD_TARGET" in
    "android-apk")
        export BUILD_TYPE="APK"
        export PLATFORM="Android"
        export CONFIG="APK Build"
        export BUILD_METHOD="BuildScript.BuildAndroidAPK"
        FILE_EXTENSION="apk"
        echo "🤖 Building Android APK (Release)"
        ;;
    "android-apk-dev")
        export BUILD_TYPE="APK"
        export PLATFORM="Android"
        export CONFIG="Development"
        export BUILD_METHOD="BuildScript.BuildAndroidDevelopment"
        FILE_EXTENSION="apk"
        echo "🔧 Building Android APK (Development + Script Debugging)"
        ;;
    "android-aab")
        export BUILD_TYPE="AAB"
        export PLATFORM="Android"
        export CONFIG="Release"
        export BUILD_METHOD="BuildScript.BuildAndroidAAB"
        FILE_EXTENSION="aab"
        echo "📦 Building Android App Bundle (Release)"
        ;;
    "ios-ipa")
        export BUILD_TYPE="IPA"
        export PLATFORM="iOS"
        export CONFIG="Release"
        export BUILD_METHOD="BuildScript.BuildIOS"
        FILE_EXTENSION="ipa"
        echo "🍎 Building iOS IPA (Release)"
        ;;
    "ios-ipa-dev")
        export BUILD_TYPE="IPA"
        export PLATFORM="iOS"
        export CONFIG="Development"
        export BUILD_METHOD="BuildScript.BuildIOSDevelopment"
        FILE_EXTENSION="ipa"
        echo "🔧 Building iOS IPA (Development + Script Debugging)"
        ;;
    "ios-appstore")
        export BUILD_TYPE="IPA"
        export PLATFORM="iOS"
        export CONFIG="AppStore"
        export BUILD_METHOD="BuildScript.BuildIOSAppStore"
        FILE_EXTENSION="ipa"
        echo "🏪 Building iOS for App Store"
        ;;
    *)
        echo "❌ ERROR: Invalid BUILD_TARGET: $BUILD_TARGET"
        echo "Valid values: android-apk, android-apk-dev, android-aab, ios-ipa, ios-ipa-dev, ios-appstore"
        exit 1
        ;;
esac

# --- COMMON CONFIGURATION ---
export BUILD_PREFIX="${BUILD_PREFIX}"
export GIT_BRANCH="${GIT_BRANCH}"
export BUILD_DIR="$WORKSPACE/Builds/${BUILD_TARGET}"  # Single directory per target, branch info in filename
export BUILD_CONFIG="${BUILD_CONFIG:-$CONFIG}"

# --- UNITY & TOOLS PATHS ---
# BIẾN UNITY_PATH ĐÃ ĐƯỢC CHUYỂN LÊN ĐẦU SCRIPT
PROJECT_PATH="$WORKSPACE/MegaRamps"
LOG_FILE="$WORKSPACE/unity_build_${BUILD_TARGET}.log"

# --- PLATFORM SPECIFIC CONFIGURATION ---
if [[ "$PLATFORM" == "Android" ]]; then
    # --- ANDROID CONFIGURATION ---
    export ANDROID_SDK_ROOT="/Volumes/Lexar/TripSoft/Programs/android-sdk"
    export ANDROID_NDK_ROOT="/Volumes/Lexar/TripSoft/Programs/android-sdk/android-ndk/android-ndk-r21d"
    export JAVA_HOME="/opt/homebrew/Cellar/openjdk@17/17.0.15"
    export GRADLE_PATH="/Volumes/Lexar/TripSoft/Programs/gradle/gradle-8.4"
    export SKIP_JDK_VERSION_CHECK=1
    
    # --- KEYSTORE CONFIGURATION ---
    # All keystore credentials are provided by Jenkins "Use secret text(s) or file(s)":
    # KEYSTORE, KEYSTORE_PASS, ALIAS_PASS, ALIAS_NAME
    
elif [[ "$PLATFORM" == "iOS" ]]; then
    # --- IOS CONFIGURATION ---
    # Xcode path will be detected automatically
    # iOS certificates and provisioning profiles should be installed on build machine
    
    # Set iOS specific environment variables if needed
    export IOS_TEAM_ID="${IOS_TEAM_ID:-}"
    export IOS_PROVISION_PROFILE="${IOS_PROVISION_PROFILE:-}"
fi

# --- BUILD INFO ---
echo "========== BUILD CONFIGURATION =========="
echo "🎯 BUILD TARGET: $BUILD_TARGET"
echo "🏷️ BUILD REQUEST ID: $BUILD_REQUEST_ID"
echo "📱 PLATFORM: $PLATFORM ($BUILD_TYPE)"
echo "⚙️ CONFIG: $CONFIG"
echo "🌿 GIT BRANCH: $GIT_BRANCH"
echo "📂 BUILD PREFIX: $BUILD_PREFIX"
echo "📁 BUILD DIR: $BUILD_DIR"
echo "🔧 BUILD METHOD: $BUILD_METHOD"
echo "📅 BUILD DATE: $(date '+%Y-%m-%d %H:%M:%S') ($(date +%y%m%d))"
echo "🎮 UNITY PATH: $UNITY_PATH"
echo "📄 PROJECT PATH: $PROJECT_PATH"
echo "📋 FILE EXTENSION: $FILE_EXTENSION"

# --- EXPECTED OUTPUT FILENAME PREDICTION ---
CURRENT_DATE=$(date +%y%m%d)
if [[ "$BUILD_TYPE" == "AAB" ]]; then
    echo "📦 EXPECTED FILENAME FORMAT: ${BUILD_PREFIX}-${GIT_BRANCH}_{APP_VERSION}_{BUNDLE_CODE}_{VERSION}.${FILE_EXTENSION}"
    echo "   (App version and bundle code will be read from Unity PlayerSettings)"
elif [[ "$FILE_EXTENSION" == "apk" ]]; then
    if [[ "$CONFIG" == "Development" ]]; then
        echo "📱 EXPECTED FILENAME FORMAT: ${BUILD_PREFIX}-${GIT_BRANCH}_${CURRENT_DATE}_debug_{VERSION}.${FILE_EXTENSION}"
        echo "🔧 EXPECTED FILENAME EXAMPLE: ${BUILD_PREFIX}-${GIT_BRANCH}_${CURRENT_DATE}_debug_01.${FILE_EXTENSION}"
    else
        echo "📱 EXPECTED FILENAME FORMAT: ${BUILD_PREFIX}-${GIT_BRANCH}_${CURRENT_DATE}_{VERSION}.${FILE_EXTENSION}"
        echo "📱 EXPECTED FILENAME EXAMPLE: ${BUILD_PREFIX}-${GIT_BRANCH}_${CURRENT_DATE}_01.${FILE_EXTENSION}"
    fi
elif [[ "$FILE_EXTENSION" == "ipa" ]]; then
    if [[ "$GIT_BRANCH" != "master" ]]; then
        echo "🍎 EXPECTED FILENAME FORMAT: ${BUILD_PREFIX}-${GIT_BRANCH}_${CURRENT_DATE}_{VERSION}.${FILE_EXTENSION}"
        echo "🍎 EXPECTED FILENAME EXAMPLE: ${BUILD_PREFIX}-${GIT_BRANCH}_${CURRENT_DATE}_01.${FILE_EXTENSION}"
    else
        echo "🍎 EXPECTED FILENAME FORMAT: ${BUILD_PREFIX}_${CURRENT_DATE}_{VERSION}.${FILE_EXTENSION}"
        echo "🍎 EXPECTED FILENAME EXAMPLE: ${BUILD_PREFIX}_${CURRENT_DATE}_01.${FILE_EXTENSION}"
    fi
fi

# --- PLATFORM SPECIFIC INFO ---
if [[ "$PLATFORM" == "Android" ]]; then
    echo "🤖 ANDROID SDK: $ANDROID_SDK_ROOT"
    echo "☕ JAVA HOME: $JAVA_HOME"
    echo "🐘 GRADLE PATH: $GRADLE_PATH"
    if [[ "$CONFIG" == "Development" ]]; then
        echo "🔧 DEVELOPMENT FEATURES: Script Debugging + Wait for Managed Debugger + Profiler"
    fi
elif [[ "$PLATFORM" == "iOS" ]]; then
    echo "🍎 XCODE VERSION: $(xcodebuild -version | head -1 2>/dev/null || echo 'Not detected')"
    if [[ "$CONFIG" == "Development" ]]; then
        echo "🔧 DEVELOPMENT FEATURES: Script Debugging + Wait for Managed Debugger + Profiler"
    elif [[ "$CONFIG" == "AppStore" ]]; then
        echo "🏪 APP STORE BUILD: Optimized for App Store submission"
    fi
fi
echo "========================================"

# --- GIT BRANCH CHECKOUT ---
echo "--- Git Branch Management ---"
cd "$WORKSPACE"

# Xử lý giá trị từ Git Parameter (ví dụ: origin/master -> master)
LOCAL_BRANCH_NAME=${GIT_BRANCH#origin/}

echo "Current git branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
echo "Requested branch from parameter: $GIT_BRANCH"
echo "Resolved local branch name: $LOCAL_BRANCH_NAME"

# First, fetch latest from remote to ensure we have all branches
echo "🔄 Fetching latest from remote..."
git fetch origin || echo "⚠️ Could not fetch from remote"

# Check if branch exists locally
if git rev-parse --verify "$LOCAL_BRANCH_NAME" >/dev/null 2>&1; then
    echo "✅ Local branch '$LOCAL_BRANCH_NAME' exists"
    if [ "$(git branch --show-current 2>/dev/null)" != "$LOCAL_BRANCH_NAME" ]; then
        echo "🔄 Switching to local branch: $LOCAL_BRANCH_NAME"
        git checkout "$LOCAL_BRANCH_NAME"
        git pull origin "$LOCAL_BRANCH_NAME" || echo "⚠️ Could not pull latest changes"
    else
        echo "✅ Already on local branch: $LOCAL_BRANCH_NAME"
        git pull origin "$LOCAL_BRANCH_NAME" || echo "⚠️ Could not pull latest changes"
    fi
# Check if branch exists on remote only
elif git rev-parse --verify "origin/$LOCAL_BRANCH_NAME" >/dev/null 2>&1; then
    echo "✅ Remote branch 'origin/$LOCAL_BRANCH_NAME' found, creating local tracking branch"
    git checkout -b "$LOCAL_BRANCH_NAME" "origin/$LOCAL_BRANCH_NAME"
    echo "✅ Created and switched to branch: $LOCAL_BRANCH_NAME"
else
    echo "❌ ERROR: Branch '$LOCAL_BRANCH_NAME' does not exist locally or on remote!"
    echo ""
    echo "📋 Available local branches:"
    git branch
    echo ""
    echo "📋 Available remote branches:"
    git branch -r
    echo ""
    echo "💡 Make sure the branch name is correct and exists on remote"
    exit 1
fi

echo "Final branch: $(git branch --show-current 2>/dev/null)"
echo "Latest commit: $(git log --oneline -1 2>/dev/null || echo 'unknown')"

# --- CLEANUP OLD BUILDS ---
cleanup_old_builds

# --- ENSURE DIRECTORIES ---
echo "--- Creating build directories ---"
mkdir -p "$BUILD_DIR"

# --- PLATFORM SPECIFIC VALIDATION ---
if [[ "$PLATFORM" == "Android" ]]; then
    # Check Android dependencies
    if [ -n "$KEYSTORE" ] && [ -f "$KEYSTORE" ]; then
        echo "✅ Android Keystore found: $KEYSTORE"
    else
        echo "⚠️ WARNING: Android Keystore environment variable not set or file not found"
        echo "    Expected: KEYSTORE environment variable from Jenkins credentials"
    fi
    
elif [[ "$PLATFORM" == "iOS" ]]; then
    # Check iOS dependencies
    if command -v xcodebuild &> /dev/null; then
        echo "✅ Xcode found: $(xcodebuild -version | head -1)"
    else
        echo "❌ ERROR: Xcode not found! iOS builds require Xcode."
        exit 1
    fi
fi

# --- UNITY BUILD COMMAND ---
echo "========== STARTING UNITY BUILD: $BUILD_TARGET =========="
echo "🚀 LAUNCHING UNITY BUILD PROCESS..."
echo "🎯 Target: $BUILD_TARGET ($PLATFORM $CONFIG)"
echo "🌿 Branch: $GIT_BRANCH"
echo "📂 Project: $PROJECT_PATH"
echo "🔧 Method: $BUILD_METHOD"
echo "📋 Log file: $LOG_FILE"
echo "⏱️ Build started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# --- BUILD TIMING ---
BUILD_START_TIME=$(date +%s)

$UNITY_PATH \
    -batchmode \
    -quit \
    -projectPath "$PROJECT_PATH" \
    -executeMethod "$BUILD_METHOD" \
    -logFile "$LOG_FILE" \
    -nographics

BUILD_RESULT=$?
echo ""
echo "🏁 Unity build process completed with exit code: $BUILD_RESULT"

# --- POST BUILD ANALYSIS ---
echo "========== BUILD COMPLETED: $BUILD_TARGET =========="
echo "🏁 Unity build exit code: $BUILD_RESULT"
echo "🎯 Build target: $BUILD_TARGET"
echo "📱 Platform: $PLATFORM ($BUILD_TYPE)"
echo "⚙️ Configuration: $CONFIG"
echo "🌿 Git branch: $GIT_BRANCH"
echo "📅 Build date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

if [ $BUILD_RESULT -eq 0 ]; then
    echo "🎉 ✅ $BUILD_TARGET BUILD SUCCESS! ✅ 🎉"
    echo "🌿 Branch: $GIT_BRANCH | ⚙️ Config: $CONFIG | 📱 Platform: $PLATFORM"
    
    # Show build duration
    show_build_duration
    
    # List generated files
    echo "--- Generated builds ---"
    if ls "$BUILD_DIR"/*.$FILE_EXTENSION 1> /dev/null 2>&1; then
        ls -la "$BUILD_DIR"/*.$FILE_EXTENSION
        
        # Find the latest build
        LATEST_BUILD=$(ls -t "$BUILD_DIR"/*.$FILE_EXTENSION 2>/dev/null | head -1)
        if [ -n "$LATEST_BUILD" ]; then
            echo "--- Latest $BUILD_TARGET build info ---"
            echo "File: $LATEST_BUILD"
            echo "Size: $(du -h "$LATEST_BUILD" | cut -f1)"
            echo "Created: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$LATEST_BUILD" 2>/dev/null || date)"
            
            # Export build info for Jenkins
            echo "LATEST_BUILD_FILE=$LATEST_BUILD" > "$WORKSPACE/build_info.properties"
            echo "BUILD_SIZE=$(stat -f%z "$LATEST_BUILD")" >> "$WORKSPACE/build_info.properties"
            echo "BUILD_DATE=$(date +%Y%m%d_%H%M%S)" >> "$WORKSPACE/build_info.properties"
            echo "BUILD_TARGET=$BUILD_TARGET" >> "$WORKSPACE/build_info.properties"
            echo "BUILD_TYPE=$BUILD_TYPE" >> "$WORKSPACE/build_info.properties"
            echo "PLATFORM=$PLATFORM" >> "$WORKSPACE/build_info.properties"
            echo "CONFIG=$CONFIG" >> "$WORKSPACE/build_info.properties"
            echo "GIT_BRANCH=$GIT_BRANCH" >> "$WORKSPACE/build_info.properties"
            echo "BUILD_REQUEST_ID=$BUILD_REQUEST_ID" >> "$WORKSPACE/build_info.properties"
            echo "FILE_EXTENSION=$FILE_EXTENSION" >> "$WORKSPACE/build_info.properties"
            
            echo "--- Build info exported to build_info.properties ---"
            cat "$WORKSPACE/build_info.properties"
            
            # Platform specific post-build info
            case "$BUILD_TARGET" in
                "android-aab")
                    echo "--- AAB Deployment Info ---"
                    echo "✅ Ready for Google Play Store upload"
                    echo "📱 Google Play will generate optimized APKs"
                    ;;
                "android-apk-dev")
                    echo "--- Development APK Info ---"
                    echo "🔧 Development build with script debugging enabled"
                    echo "🐛 Wait for managed debugger enabled"
                    echo "📱 Ready for testing and debugging"
                    ;;
                "ios-ipa-dev")
                    echo "--- iOS Development IPA Info ---"
                    echo "🔧 Development build with script debugging enabled"
                    echo "🐛 Wait for managed debugger enabled"
                    echo "📱 Ready for testing and debugging"
                    ;;
                "ios-appstore")
                    echo "--- App Store Deployment Info ---"
                    echo "✅ Ready for App Store Connect upload"
                    echo "🔒 Make sure certificates and provisioning profiles are valid"
                    ;;
            esac
        else
            echo "⚠️  WARNING: No $BUILD_TARGET build file found with today's date pattern"
        fi
    else
        echo "❌ No $BUILD_TARGET build files found in $BUILD_DIR"
    fi
    
    # Show build directory contents
    echo "--- Build directory contents ---"
    ls -la "$BUILD_DIR" 2>/dev/null || echo "Build directory is empty"
    
else
    echo "❌ $BUILD_TARGET BUILD FAILED!"
    
    # Show build duration even on failure
    show_build_duration
    
    echo "--- Error analysis ---"
    
    # Show Unity log
    if [ -f "$LOG_FILE" ]; then
        echo "--- Last 50 lines of Unity log ---"
        tail -50 "$LOG_FILE"
        
        echo "--- Searching for errors ---"
        if grep -i "error\|exception\|failed" "$LOG_FILE" | tail -10; then
            echo "Found errors above"
        else
            echo "No obvious errors found in log"
        fi
    else
        echo "No Unity log file found at $LOG_FILE"
    fi
    
    # Platform specific error checking
    if [[ "$PLATFORM" == "Android" && "$BUILD_RESULT" -ne 0 ]]; then
        echo "--- Android Build Troubleshooting ---"
        echo "Check: Android SDK, NDK, JDK paths"
        echo "Check: Keystore file and credentials"
        echo "Check: Gradle version compatibility"
    elif [[ "$PLATFORM" == "iOS" && "$BUILD_RESULT" -ne 0 ]]; then
        echo "--- iOS Build Troubleshooting ---"
        echo "Check: Xcode installation and command line tools"
        echo "Check: iOS certificates and provisioning profiles"
        echo "Check: Team ID and bundle identifier"
    fi
fi

echo "========== JENKINS $BUILD_TARGET BUILD SCRIPT END =========="
exit $BUILD_RESULT 