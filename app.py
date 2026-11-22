# app.py - 主入口与路由
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash

from config import Config
from database import db
from models import Book, Borrow

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


# ---------- 首页：图书列表 ----------
@app.route("/")
def index():
    books = Book.query.order_by(Book.id.desc()).all()
    return render_template("index.html", books=books)


# ---------- 图书录入 ----------
@app.route("/add", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip()
        category = request.form.get("category", "").strip()
        stock_raw = request.form.get("stock", "0").strip()

        # 基础校验
        if not title or not author or not isbn or not category:
            flash("所有字段均为必填项", "error")
            return redirect(url_for("add_book"))

        try:
            stock = int(stock_raw)
            if stock < 0:
                raise ValueError
        except ValueError:
            flash("库存数量必须为非负整数", "error")
            return redirect(url_for("add_book"))

        # 不可重复录入同一 ISBN
        if Book.query.filter_by(isbn=isbn).first():
            flash(f"ISBN {isbn} 已存在，不可重复录入", "error")
            return redirect(url_for("add_book"))

        book = Book(title=title, author=author, isbn=isbn,
                    category=category, stock=stock)
        db.session.add(book)
        db.session.commit()
        flash(f"《{title}》录入成功", "success")
        return redirect(url_for("index"))

    return render_template("add_book.html")


# ---------- 图书查询（模糊检索） ----------
@app.route("/search")
def search():
    keyword = request.args.get("q", "").strip()
    books = []
    if keyword:
        like = f"%{keyword}%"
        books = Book.query.filter(
            db.or_(
                Book.title.like(like),
                Book.author.like(like),
                Book.isbn.like(like),
            )
        ).all()
    return render_template("search.html", books=books, keyword=keyword)


# ---------- 借出登记 ----------
@app.route("/borrow/<int:book_id>", methods=["GET", "POST"])
def borrow_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == "POST":
        borrower = request.form.get("borrower", "").strip()
        if not borrower:
            flash("借阅人不能为空", "error")
            return redirect(url_for("borrow_book", book_id=book_id))

        # 不可借出库存为 0 的书
        if book.stock <= 0:
            flash("该书库存为 0，无法借出", "error")
            return redirect(url_for("index"))

        book.stock -= 1
        record = Borrow(book_id=book.id, borrower=borrower,
                        borrow_time=datetime.now(), is_returned=False)
        db.session.add(record)
        db.session.commit()
        flash(f"《{book.title}》已借给 {borrower}", "success")
        return redirect(url_for("index"))

    return render_template("borrow.html", book=book)


# ---------- 借阅记录 / 归还 ----------
@app.route("/records")
def records():
    # 查询条件：借阅人 / 书名 / 状态
    borrower = request.args.get("borrower", "").strip()
    book_title = request.args.get("book_title", "").strip()
    status = request.args.get("status", "").strip()   # all / borrowed / returned / overdue

    query = Borrow.query.join(Book, Borrow.book_id == Book.id)

    if borrower:
        query = query.filter(Borrow.borrower.like(f"%{borrower}%"))
    if book_title:
        query = query.filter(Book.title.like(f"%{book_title}%"))
    if status == "borrowed":
        query = query.filter(Borrow.is_returned.is_(False))
    elif status == "returned":
        query = query.filter(Borrow.is_returned.is_(True))

    all_records = query.order_by(Borrow.id.desc()).all()

    # 逾期判断：未归还 且 借出时间超过 LOAN_DAYS
    now = datetime.now()
    loan_days = app.config.get("LOAN_DAYS", 30)
    rows = []
    for r in all_records:
        overdue_days = 0
        if not r.is_returned:
            elapsed = (now - r.borrow_time).days
            if elapsed > loan_days:
                overdue_days = elapsed - loan_days
        rows.append({"record": r, "overdue_days": overdue_days})

    # 若选择「逾期」状态，只保留逾期行
    if status == "overdue":
        rows = [x for x in rows if x["overdue_days"] > 0]

    return render_template("records.html", rows=rows,
                           borrower=borrower, book_title=book_title,
                           status=status, loan_days=loan_days)


@app.route("/return/<int:record_id>", methods=["POST"])
def return_book(record_id):
    record = Borrow.query.get_or_404(record_id)
    if record.is_returned:
        flash("该记录已归还，无需重复操作", "error")
        return redirect(url_for("records"))

    record.is_returned = True
    record.return_time = datetime.now()
    # 归还时恢复库存
    record.book.stock += 1
    db.session.commit()
    flash(f"《{record.book.title}》已归还", "success")
    return redirect(url_for("records"))


# ---------- 删除图书 ----------
@app.route("/delete/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)

    # 若有未归还的借阅记录，禁止删除
    active = Borrow.query.filter_by(book_id=book.id, is_returned=False).first()
    if active:
        flash(f"《{book.title}》尚有未归还的借阅记录，无法删除", "error")
        return redirect(url_for("index"))

    # 先删除该书的借阅历史，再删除图书（避免外键约束报错）
    Borrow.query.filter_by(book_id=book.id).delete()
    db.session.delete(book)
    db.session.commit()
    flash(f"《{book.title}》已删除", "success")
    return redirect(url_for("index"))


# ---------- 逾期统计 ----------
@app.route("/overdue")
def overdue():
    now = datetime.now()
    loan_days = app.config.get("LOAN_DAYS", 30)

    # 所有未归还记录
    active = Borrow.query.filter(Borrow.is_returned.is_(False)) \
                         .order_by(Borrow.borrow_time.asc()).all()

    rows = []
    for r in active:
        elapsed = (now - r.borrow_time).days
        overdue_days = elapsed - loan_days
        if overdue_days > 0:
            rows.append({"record": r, "elapsed": elapsed, "overdue_days": overdue_days})

    # 按逾期天数降序
    rows.sort(key=lambda x: x["overdue_days"], reverse=True)

    # 汇总统计
    total_borrowed = Borrow.query.count()
    total_active = len(active)
    total_overdue = len(rows)
    total_returned = Borrow.query.filter(Borrow.is_returned.is_(True)).count()

    stats = {
        "total_borrowed": total_borrowed,
        "total_active": total_active,
        "total_overdue": total_overdue,
        "total_returned": total_returned,
        "loan_days": loan_days,
    }

    return render_template("overdue.html", rows=rows, stats=stats)


# ---------- 编辑图书 ----------
@app.route("/edit/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip()
        category = request.form.get("category", "").strip()
        stock_raw = request.form.get("stock", "0").strip()

        # 基础校验
        if not title or not author or not isbn or not category:
            flash("所有字段均为必填项", "error")
            return redirect(url_for("edit_book", book_id=book_id))

        try:
            stock = int(stock_raw)
            if stock < 0:
                raise ValueError
        except ValueError:
            flash("库存数量必须为非负整数", "error")
            return redirect(url_for("edit_book", book_id=book_id))

        # 不可与其他图书的 ISBN 重复（排除自身）
        exist = Book.query.filter(Book.isbn == isbn, Book.id != book.id).first()
        if exist:
            flash(f"ISBN {isbn} 已被《{exist.title}》使用，不可重复", "error")
            return redirect(url_for("edit_book", book_id=book_id))

        book.title = title
        book.author = author
        book.isbn = isbn
        book.category = category
        book.stock = stock
        db.session.commit()
        flash(f"《{title}》修改成功", "success")
        return redirect(url_for("index"))

    return render_template("edit_book.html", book=book)


# ---------- 初始化数据库 ----------
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)