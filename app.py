from flask import Flask, render_template, request,redirect,session
from werkzeug.utils import secure_filename
import os

from models import db, Rubbish,User,Feedback
from ai import recognize_image

import random
from models import Question, LotteryRecord,QuizRecord

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rubbish.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '123456'


db.init_app(app)

UPLOAD_FOLDER = "uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# ======================
# 首页（判断登录状态）
# ======================
@app.route('/')
def index():
    return render_template(
        'index.html',
        user_id=session.get('user_id')
    )

# ======================
# 登录
# ======================
@app.route('/login', methods=['GET', 'POST'])
def login():

    next_url = request.args.get('next')

    if request.method == 'POST':

        phone = request.form['phone']
        password = request.form['password']

        user = User.query.filter_by(phone=phone).first()

        if not user:
            return redirect('/register')

        if user.password != password:
            return "密码错误"

        session['user_id'] = user.id
        session['nickname'] = user.nickname
        session['is_admin'] = user.is_admin
        # ⭐关键：回到原页面
        return redirect(next_url or '/')

    return render_template('login.html')

# ======================
# 退出登录
# ======================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
# ======================
# 注册
# ======================
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        phone = request.form['phone']
        nickname = request.form['nickname']
        password = request.form['password']

        user = User.query.filter_by(phone=phone).first()

        if user:
            return "该手机号已注册"

        new_user = User(
            phone=phone,
            nickname=nickname,
            password=password
        )

        db.session.add(new_user)
        db.session.commit()

        # 自动登录
        session['user_id'] = new_user.id
        session['nickname'] = new_user.nickname

        return redirect('/')

    return render_template('register.html')


@app.route('/ai')
def ai():
    return render_template('ai.html')


@app.route('/result')
def result():
    return render_template('result.html')


@app.route('/feedback')
def feedback():

    if not session.get('user_id'):
        return redirect('/login')

    return render_template(
        'feedback.html',
        name=session.get('ai_name'),
        wrong_category=session.get('ai_category'),
        image_path=session.get('ai_image_path')
    )
@app.route('/feedback_submit', methods=['POST'])
def feedback_submit():

    if not session.get('user_id'):
        return redirect('/login')

    user_id = session['user_id']

    name = request.form.get('name')
    wrong_category = request.form.get('wrong_category')
    correct_category = request.form.get('correct_category')

    fb = Feedback(
        user_id=user_id,
        name=name,
        wrong_category=wrong_category,
        correct_category=correct_category
    )

    db.session.add(fb)
    db.session.commit()

    # ⭐ 存session用于返回AI结果页
    session['feedback_success'] = True

    return redirect('/ai_result')

@app.route('/info')
def info():
    return render_template('information.html')


@app.route('/quiz')
def quiz():

    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    user = User.query.get(user_id)

    # 第一次进入答题才初始化
    if 'score' not in session:
        session['score'] = 0

    if 'quiz_count' not in session:
        session['quiz_count'] = 1

    if 'answered' not in session:
        session['answered'] = False

    # 当前没有题目才抽新题
    if 'current_question' not in session:

        question = random.choice(Question.query.all())

        session['current_question'] = question.id

    else:

        question = Question.query.get(
            session['current_question']
        )

    return render_template(
        'quiz.html',
        q=question,
        score=session['score'],
        total=user.total_points,
        q_index=session['quiz_count'],
        result=None,
        correct_answer=None
    )
@app.route('/next_question')
def next_question():

    session['quiz_count'] += 1
    session['answered'] = False

    question = random.choice(Question.query.all())
    session['current_question'] = question.id

    return render_template(
        'quiz.html',
        q=question,
        result=None,
        correct_answer=None,
        score=session['score'],
        total=User.query.get(session['user_id']).total_points,
        q_index=session['quiz_count']
    )
@app.route('/end_quiz')
def end_quiz():

    user_id = session.get('user_id')
    user = User.query.get(user_id)

    score = session.get('score', 0)

    session.pop('score', None)
    session.pop('quiz_count', None)
    session.pop('current_question', None)
    session.pop('answered', None)

    return render_template(
        "result.html",
        name="本轮结束",
        category=f"本轮得分：{score}",
        description=f"累计总分：{user.total_points}",
        is_quiz_end = True
    )
@app.route('/me')
def me():

    user = User.query.get(session['user_id'])

    records = QuizRecord.query.filter_by(
        user_id=user.id
    ).all()

    print("records:", records)   # ⭐加这个

    return render_template(
        'me.html',
        user=user,
        records=records
    )
########################搜索框逻辑
@app.route('/search')
def search():

    keyword = request.args.get('keyword')

    item = Rubbish.query.filter(
        Rubbish.name.like(f'%{keyword}%')
    ).first()

    if item:

        # ⭐关键：统一存 session（和 AI 一样）
        session['ai_name'] = item.name
        session['ai_category'] = item.category
        session['ai_description'] = item.description
        session['ai_image_path'] = None   # 搜索没有图片

        return render_template(
            'result.html',
            name=item.name,
            category=item.category,
            description=item.description
        )

    return render_template(
        'result.html',
        name=keyword,
        category='未找到',
        description='数据库中没有该垃圾信息'
    )
# ======================
# AI上传核心逻辑
# ======================

@app.route('/ai_upload', methods=['POST'])
def ai_upload():

    file = request.files['image']
    # ❗没有上传文件
    if not file or file.filename == '':
        return "<script>alert('未上传图片');window.location.href='/ai';</script>"
    filename = secure_filename(file.filename)

    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    session['ai_image_path'] = path
    # AI识别
    name = recognize_image(path)

    item = Rubbish.query.filter_by(name=name).first()

    if item:
        category = item.category
        description = item.description
    else:
        category = "未知"
        description = "数据库未收录该垃圾"

    # ⭐关键：存 session
    session['ai_name'] = name
    session['ai_category'] = category
    session['ai_description'] = description

    # ⭐关键：跳转
    return redirect('/ai_result')
@app.route('/ai_result')
def ai_result():

    name = session.get('ai_name', '')
    category = session.get('ai_category', '')
    description = session.get('ai_description', '')

    return render_template(
        "result.html",
        name=name,
        category=category,
        description=description,
        feedback_success=session.pop('feedback_success', False)
    )
@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():

    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    if session.get('answered'):
        return redirect('/quiz')

    user = User.query.get(user_id)

    qid = session.get('current_question')
    question = Question.query.get(qid)

    user_answer = request.form.get('answer')
    correct = (user_answer == question.answer)

    if correct:
        session['score'] += 10
        user.total_points += 10
        db.session.commit()

    session['answered'] = True

    # ❗❗❗关键：直接返回 quiz.html，不要 redirect
    return render_template(
        'quiz.html',
        q=question,
        result=correct,
        correct_answer=question.answer,
        score=session['score'],
        total=user.total_points,
        q_index=session['quiz_count']
    )
@app.route('/lottery', methods=['POST'])
def lottery():

    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    user = User.query.get(user_id)

    if user.total_points < 10:
        return "积分不足，无法抽奖"

    # 扣积分
    user.total_points -= 10

    result = random.choices(
        population=[
            "谢谢参与",
            "再来一次",
            "+5积分",
            "+10积分",
            "环保达人徽章",
            "幸运空投"
        ],
        weights=[40, 25, 20, 10, 4, 1],
        k=1
    )[0]

    # 加积分
    if result == "+5积分":
        user.total_points += 5
        change = -5
    elif result == "+10积分":
        user.total_points += 10
        change = 0
    else:
        change = -10

    # ⭐⭐⭐新增：流水记录（关键）
    db.session.add(QuizRecord(
        user_id=user.id,
        score=change,
        correct=1,   # 1 = 抽奖
        total=user.total_points
    ))

    # 你原来的也可以保留（不影响）
    db.session.add(LotteryRecord(
        user_id=user.id,
        cost=10,
        result=result
    ))

    db.session.commit()

    return render_template(
        "lottery_result.html",
        result=result,
        total=user.total_points
    )
@app.route('/suggest')
def suggest():

    keyword = request.args.get('keyword', '')

    if not keyword:
        return []

    items = Rubbish.query.filter(
        Rubbish.name.like(f'%{keyword}%')
    ).limit(5).all()

    return [
        {
            "name": i.name,
            "category": i.category
        }
        for i in items
    ]
@app.route('/admin')
def admin():

    if not session.get('user_id'):
        return redirect('/login')

    if not session.get('is_admin'):
        return "无权限访问"

    return render_template('admin.html')
@app.route('/admin_feedback')
def admin_feedback():

    if not session.get('user_id'):
        return redirect('/login')

    if not session.get('is_admin'):
        return "无权限访问"

    feedback_list = Feedback.query.order_by(Feedback.id.desc()).all()

    return render_template(
        'admin_feedback.html',
        feedback_list=feedback_list
    )


@app.route('/admin_rubbish')
def admin_rubbish():

    if not session.get('user_id'):
        return redirect('/login')

    if not session.get('is_admin'):
        return "无权限访问"

    items = Rubbish.query.order_by(Rubbish.id.desc()).all()

    return render_template(
        'admin_rubbish.html',
        items=items
    )
@app.route('/admin_rubbish_add', methods=['POST'])
def admin_rubbish_add():

    if not session.get('is_admin'):
        return "无权限"

    name = request.form.get('name')
    category = request.form.get('category')
    description = request.form.get('description')

    new_item = Rubbish(
        name=name,
        category=category,
        description=description
    )

    db.session.add(new_item)
    db.session.commit()

    return redirect('/admin_rubbish')
@app.route('/admin_rubbish_delete/<int:item_id>')
def admin_rubbish_delete(item_id):

    if not session.get('is_admin'):
        return "无权限"

    item = Rubbish.query.get(item_id)

    if item:
        db.session.delete(item)
        db.session.commit()

    return redirect('/admin_rubbish')
@app.route('/admin_question')
def admin_question():

    if not session.get('user_id'):
        return redirect('/login')

    if not session.get('is_admin'):
        return "无权限访问"

    questions = Question.query.order_by(Question.id.desc()).all()

    return render_template(
        'admin_question.html',
        questions=questions
    )

@app.route('/admin_question_add', methods=['POST'])
def admin_question_add():

    if not session.get('is_admin'):
        return "无权限"

    q = request.form.get('question')
    a = request.form.get('option_a')
    b = request.form.get('option_b')
    c = request.form.get('option_c')
    answer = request.form.get('answer')

    new_q = Question(
        question=q,
        option_a=a,
        option_b=b,
        option_c=c,
        answer=answer
    )

    db.session.add(new_q)
    db.session.commit()

    return redirect('/admin_question')
@app.route('/admin_question_delete/<int:q_id>')
def admin_question_delete(q_id):

    if not session.get('is_admin'):
        return "无权限"

    q = Question.query.get(q_id)

    if q:
        db.session.delete(q)
        db.session.commit()

    return redirect('/admin_question')
@app.route('/admin_question_edit/<int:q_id>')
def admin_question_edit(q_id):

    if not session.get('is_admin'):
        return "无权限"

    q = Question.query.get(q_id)

    return render_template(
        'admin_question_edit.html',
        q=q
    )
@app.route('/admin_question_update/<int:q_id>', methods=['POST'])
def admin_question_update(q_id):

    if not session.get('is_admin'):
        return "无权限"

    q = Question.query.get(q_id)

    q.question = request.form.get('question')
    q.option_a = request.form.get('option_a')
    q.option_b = request.form.get('option_b')
    q.option_c = request.form.get('option_c')
    q.answer = request.form.get('answer')

    db.session.commit()

    return redirect('/admin_question')
@app.route('/admin_users')
def admin_users():

    if not session.get('user_id'):
        return redirect('/login')

    if not session.get('is_admin'):
        return "无权限访问"

    users = User.query.order_by(User.id.desc()).all()

    return render_template(
        'admin_users.html',
        users=users
    )
@app.route('/admin_set_admin/<int:user_id>')
def admin_set_admin(user_id):

    if not session.get('is_admin'):
        return "无权限"

    user = User.query.get(user_id)

    if user:
        user.is_admin = True
        db.session.commit()

    return redirect('/admin_users')
@app.route('/admin_cancel_admin/<int:user_id>')
def admin_cancel_admin(user_id):

    if not session.get('is_admin'):
        return "无权限"

    user = User.query.get(user_id)

    if user:
        user.is_admin = False
        db.session.commit()

    return redirect('/admin_users')
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)