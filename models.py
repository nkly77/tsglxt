# models.py - 数据模型
from datetime import datetime
from database import db

class Book(db.Model):
    """图书模型"""
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)          # 书名
    author = db.Column(db.String(120), nullable=False)         # 作者
    isbn = db.Column(db.String(32), unique=True, nullable=False)  # ISBN 唯一
    category = db.Column(db.String(80), nullable=False)        # 分类
    stock = db.Column(db.Integer, default=0, nullable=False)   # 库存数量

    borrows = db.relationship("Borrow", backref="book", lazy=True)

    def __repr__(self):
        return f"<Book {self.title}>"


class Borrow(db.Model):
    """借阅记录模型"""
    __tablename__ = "borrows"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    borrower = db.Column(db.String(120), nullable=False)       # 借阅人
    borrow_time = db.Column(db.DateTime, default=datetime.now) # 借出时间
    return_time = db.Column(db.DateTime, nullable=True)        # 归还时间
    is_returned = db.Column(db.Boolean, default=False)         # 是否已归还

    def __repr__(self):
        return f"<Borrow {self.borrower} - {self.book_id}>"