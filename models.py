from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# 用户
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True)
    password = db.Column(db.String(255))
    nickname = db.Column(db.String(50))
    total_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

# 垃圾知识库（核心）
class Rubbish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)   # 电池 / 香蕉 / 纸巾
    category = db.Column(db.String(50))             # 有害 / 厨余 / 可回收
    description = db.Column(db.Text)                # 说明


# 反馈（保留）
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    name = db.Column(db.String(100))
    wrong_category = db.Column(db.String(50))
    correct_category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 题库
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255))
    option_a = db.Column(db.String(100))
    option_b = db.Column(db.String(100))
    option_c = db.Column(db.String(100))
    answer = db.Column(db.String(50))


# 答题记录
class QuizRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    score = db.Column(db.Integer)
    correct = db.Column(db.Integer)
    total = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# 用户积分
class LotteryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    cost = db.Column(db.Integer)
    result = db.Column(db.String(100))
    created_at = db.Column(db.DateTime)