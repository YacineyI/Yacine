
"""
Configuration file for bot credentials and settings
Contains all privacy-related settings and sensitive information
"""

import os

class Config:
    # === Bot Owner & Privacy Settings ===
    BOT_OWNER = ""  # you name
    ADMIN_USERS = [""]  # قائمة المديرين
    VIP_USERS = [""]  # قائمة المستخدمين المميزين
    BANNED_USERS = []  # قائمة المحظورين
    
    # === Bot Credentials (Sensitive) ===
    # يُنصح بوضع هذه القيم في Secrets tool في Replit
    ROOM_ID = os.getenv("ROOM_ID", "6897a0d92aa5825e0e244dd9") # id room here 
    BOT_TOKEN = os.getenv("BOT_TOKEN", "e2abeba5ea19b4fe0cf8d9e54e71b9e5e2c2b6f86df82580485ce88fde08c283") # token here
    
    # === Privacy & Security Settings ===
    ENABLE_WELCOME_MESSAGES = True
    ENABLE_GOODBYE_MESSAGES = True
    ENABLE_COMMANDS_FOR_ALL = True  # السماح للجميع باستخدام الأوامر
    ENABLE_REACTIONS_FOR_ALL = True  # السماح للجميع بردود الفعل
    MODERATOR_ONLY_COMMANDS = ["/admin", "/ban", "/unban", "/kick", "/bring", "/follow"]
    
    # === Bot Behavior Settings ===
    MAX_EMOTE_LOOPS_PER_USER = 1  # عدد الحركات المتزامنة لكل مستخدم
    EMOTE_LOOP_INTERVAL = 3  # الفترة بين الحركات بالثواني
    AUTO_STOP_EMOTES_ON_LEAVE = True  # إيقاف الحركات عند مغادرة المستخدم
    
    # === Message Filters & Moderation ===
    ENABLE_WORD_FILTER = False
    BLOCKED_WORDS = []  # كلمات محظورة
    SPAM_PROTECTION = True
    MAX_MESSAGES_PER_MINUTE = 10
    
    # === Bot Position & Movement ===
    BOT_SPAWN_POSITION = {
        "x": 8.50,
        "y": 0.00, 
        "z": 5.00,
        "facing": "FrontRight"
    }
    ENABLE_BOT_MOVEMENT = True
    
    # === Random Movement Settings ===
    ENABLE_RANDOM_MOVEMENT = True  # تفعيل/إلغاء التحرك العشوائي
    RANDOM_MOVEMENT_INTERVAL = 60  # كل كم ثانية (60 = دقيقة واحدة)
    RANDOM_MOVEMENT_RADIUS = 3.0   # نصف قطر التحرك من المكان الأصلي
    
    # === Web Server Configuration ===
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 5000
    WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY", "your-secret-key-change-this-in-production")
    
    # === File Management Settings ===
    BOT_FILE = "main"
    BOT_CLASS = "Bot"
    UPLOAD_FOLDER = "uploads"
    ALLOWED_EXTENSIONS = {"py", "json", "txt", "md", "html", "css", "js"}
    MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
    
    # === Backup & Security ===
    AUTO_BACKUP = True
    BACKUP_INTERVAL_HOURS = 6
    KEEP_BACKUP_DAYS = 7
    PROTECT_CORE_FILES = ["main.py", "config.py"]  # ملفات محمية من الحذف
    
    # === Logging & Monitoring ===
    ENABLE_LOGGING = True
    LOG_CHAT_MESSAGES = True
    LOG_USER_ACTIONS = True
    LOG_BOT_ERRORS = True
    
    # === API Keys & External Services ===
    # يُنصح بوضع هذه في Secrets tool
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    
    # === Feature Toggles ===
    FEATURES = {
        "dance_commands": True,
        "reaction_commands": True,
        "admin_commands": True,
        "file_management": True,
        "auto_restart": True,
        "web_interface": True,
        "user_stats": False,
        "custom_commands": False
    }
    
    # === Rate Limiting ===
    RATE_LIMITS = {
        "commands_per_minute": 20,
        "reactions_per_minute": 10,
        "emote_changes_per_minute": 5
    }
    
    # === Notification Settings ===
    NOTIFICATIONS = {
        "new_user_join": True,
        "user_leave": True,
        "bot_restart": False,
        "error_alerts": True
    }
    
    @classmethod
    def is_owner(cls, username):
        """Check if user is the bot owner"""
        return username == cls.BOT_OWNER
    
    @classmethod 
    def is_admin(cls, username):
        """Check if user is an admin"""
        return username in cls.ADMIN_USERS
    
    @classmethod
    def is_vip(cls, username):
        """Check if user is VIP"""
        return username in cls.VIP_USERS
    
    @classmethod
    def is_banned(cls, username):
        """Check if user is banned"""
        return username in cls.BANNED_USERS
    
    @classmethod
    def can_use_command(cls, username, command):
        """Check if user can use specific command"""
        if cls.is_banned(username):
            return False
        if command in cls.MODERATOR_ONLY_COMMANDS:
            return cls.is_admin(username) or cls.is_owner(username)
        return True
