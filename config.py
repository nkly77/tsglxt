# config.py - 配置模块
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "tsgkxt-secret-key-change-me"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "library.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
        # 借阅期限（天），超过即视为逾期
    LOAN_DAYS = 30
        # 批量导入上传目录
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    ALLOWED_EXTENSIONS = {"csv", "xlsx"}