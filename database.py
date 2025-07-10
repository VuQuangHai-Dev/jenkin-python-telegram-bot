import sqlite3
import config
import logging
from typing import Optional, Tuple, List, Dict, Any
import security # Added missing import

# Cấu hình logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Khởi tạo database nếu chưa tồn tại."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        
        # Tạo bảng users nếu chưa tồn tại
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_user_id INTEGER PRIMARY KEY,
            jenkins_url TEXT NOT NULL,
            jenkins_userid TEXT NOT NULL,
            jenkins_token TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Tạo bảng groups nếu chưa tồn tại
        # Lưu ý: Không sử dụng PRIMARY KEY cho telegram_group_id
        # để cho phép nhiều nhóm sử dụng cùng một job
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_group_id INTEGER NOT NULL,
            jenkins_job_path TEXT NOT NULL,
            setup_by_user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (setup_by_user_id) REFERENCES users (telegram_user_id),
            UNIQUE(telegram_group_id, jenkins_job_path)
        )
        """)
        
        # Tạo bảng build_requests để lưu thông tin yêu cầu build
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS build_requests (
            build_id TEXT PRIMARY KEY,
            jenkins_job_path TEXT NOT NULL,
            build_number INTEGER,
            telegram_group_id INTEGER NOT NULL,
            requested_by_user_id INTEGER NOT NULL,
            build_target TEXT, -- Thêm cột mới để lưu build target
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (requested_by_user_id) REFERENCES users (telegram_user_id)
        )
        """)
        
        conn.commit()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

def save_user(user_id: int, jenkins_url: str, jenkins_userid: str, encrypted_token: str) -> bool:
    """Lưu hoặc cập nhật thông tin đăng nhập Jenkins của người dùng."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        
        # Kiểm tra xem người dùng đã tồn tại chưa
        cursor.execute("SELECT 1 FROM users WHERE telegram_user_id = ?", (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Cập nhật thông tin nếu người dùng đã tồn tại
            cursor.execute("""
                UPDATE users 
                SET jenkins_url = ?, jenkins_userid = ?, jenkins_token = ? 
                WHERE telegram_user_id = ?
            """, (jenkins_url, jenkins_userid, encrypted_token, user_id))
        else:
            # Thêm người dùng mới
            cursor.execute("""
                INSERT INTO users (telegram_user_id, jenkins_url, jenkins_userid, jenkins_token)
                VALUES (?, ?, ?, ?)
            """, (user_id, jenkins_url, jenkins_userid, encrypted_token))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error while saving user: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_user_credentials(user_id: int) -> Optional[Dict[str, str]]:
    """Lấy thông tin đăng nhập Jenkins của người dùng dưới dạng dictionary."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        conn.row_factory = sqlite3.Row  # Trả về kết quả dưới dạng dictionary-like
        cursor = conn.cursor()
        cursor.execute("""
            SELECT jenkins_url, jenkins_userid, jenkins_token 
            FROM users 
            WHERE telegram_user_id = ?
        """, (user_id,))
        result = cursor.fetchone()
        
        if result:
            # Giải mã token trước khi trả về
            decrypted_token = security.decrypt_data(result['jenkins_token'])
            if decrypted_token is None:
                logger.error(f"Failed to decrypt token for user {user_id}")
                return None

            # SỬA LỖI: Chuẩn hóa key trả về để khớp với tên cột DB
            return {
                'jenkins_url': result['jenkins_url'],
                'jenkins_userid': result['jenkins_userid'],
                'jenkins_token': decrypted_token
            }
        return None
    except sqlite3.Error as e:
        logger.error(f"Database error while fetching user credentials: {e}")
        return None
    finally:
        if conn:
            conn.close()

def delete_user(user_id: int) -> bool:
    """Xóa thông tin đăng nhập Jenkins của người dùng."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE telegram_user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error while deleting user: {e}")
        return False
    finally:
        if conn:
            conn.close()

def is_user_logged_in(user_id: int) -> bool:
    """Kiểm tra xem người dùng đã đăng nhập chưa."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE telegram_user_id = ?", (user_id,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"Database error while checking user login status: {e}")
        return False
    finally:
        if conn:
            conn.close()

def save_group_config(group_id: int, job_path: str, user_id: int) -> bool:
    """Lưu cấu hình liên kết giữa nhóm Telegram và Jenkins job."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        
        # Xóa tất cả cấu hình cũ của nhóm này
        cursor.execute("""
            DELETE FROM groups 
            WHERE telegram_group_id = ?
        """, (group_id,))
        
        # Thêm cấu hình mới
        cursor.execute("""
            INSERT INTO groups (telegram_group_id, jenkins_job_path, setup_by_user_id)
            VALUES (?, ?, ?)
        """, (group_id, job_path, user_id))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error while saving group config: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_group_config(group_id: int) -> Optional[Tuple[str, int]]:
    """Lấy cấu hình Jenkins job của một nhóm Telegram."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT jenkins_job_path, setup_by_user_id 
            FROM groups 
            WHERE telegram_group_id = ?
        """, (group_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Database error while fetching group config: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_group_by_job_path(job_path: str) -> Optional[Tuple[int, int]]:
    """
    Lấy thông tin nhóm Telegram đã setup một Jenkins job (phiên bản cũ).
    Chỉ giữ lại để tương thích ngược với code cũ.
    """
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT telegram_group_id, setup_by_user_id 
            FROM groups 
            WHERE jenkins_job_path = ?
            LIMIT 1
        """, (job_path,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Database error while fetching group by job path: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_groups_by_job_path(job_path: str) -> List[Tuple[int, int]]:
    """
    Lấy tất cả các nhóm Telegram đã setup một Jenkins job.
    Chỉ sử dụng cho mục đích tham khảo, không dùng để gửi thông báo.
    """
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT telegram_group_id, setup_by_user_id 
            FROM groups 
            WHERE jenkins_job_path = ?
        """, (job_path,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Database error while fetching groups by job path: {e}")
        return []
    finally:
        if conn:
            conn.close()

def save_build_request(build_request_id: str, jenkins_job_path: str, telegram_group_id: int, requested_by_user_id: int, build_target: str) -> bool:
    """Lưu thông tin về một yêu cầu build, bao gồm cả build target."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO build_requests (build_id, jenkins_job_path, telegram_group_id, requested_by_user_id, build_target)
            VALUES (?, ?, ?, ?, ?)
        """, (build_request_id, jenkins_job_path, telegram_group_id, requested_by_user_id, build_target))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error while saving build request: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_build_request(build_request_id: str) -> Optional[Dict[str, Any]]:
    """Lấy thông tin của một yêu cầu build cụ thể."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        conn.row_factory = sqlite3.Row  # Để trả về dict thay vì tuple
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM build_requests
            WHERE build_id = ?
        """, (build_request_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Database error while getting build request: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_latest_build_request(job_path: str, build_number: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Lấy yêu cầu build gần nhất cho một job cụ thể.
    Nếu build_number được cung cấp, sẽ tìm yêu cầu build với số build đó.
    Nếu không, sẽ lấy yêu cầu build gần nhất theo thời gian.
    """
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if build_number is not None:
            cursor.execute("""
                SELECT * FROM build_requests
                WHERE jenkins_job_path = ? AND build_number = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (job_path, build_number))
        else:
            cursor.execute("""
                SELECT * FROM build_requests
                WHERE jenkins_job_path = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (job_path,))
            
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Database error while getting latest build request: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_build_request_with_build_number(build_request_id: str, build_number: int) -> bool:
    """Cập nhật số build cho yêu cầu build."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE build_requests
            SET build_number = ?
            WHERE build_id = ?
        """, (build_number, build_request_id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error while updating build request: {e}")
        return False
    finally:
        if conn:
            conn.close()