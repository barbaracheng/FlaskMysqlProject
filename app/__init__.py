from flask import Flask, redirect, json, jsonify
from flask import request, session
from flask.templating import render_template
import pymysql
from datetime import timedelta
import os

# 打开数据库连接
db = pymysql.connect(host='127.0.0.1', user='root', password='123456', db='dbap')
# 使用 cursor() 方法创建一个游标对象 cur
cur = db.cursor()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # 配置7天有效


@app.route('/', methods=['GET'])
def index():
    return render_template('login.html')


# 登录
@app.route('/login', methods=['POST'])
def login():
    # usertype = data['usertype']
    # username = request.form['username']
    # password = request.form['password']
    # usertype = request.form['usertype']
    data = json.loads(request.get_data(as_text=True))
    username = data['username']
    password = data['password']
    sql = """select * from userinfo where username='%s'""" % username
    cur.execute(sql)
    user = cur.fetchone()
    if user is None:
        return jsonify({'status': 'error', 'msg': '用户名不存在！'})
    elif user[1] != password:
        return jsonify({'status': 'error', 'msg': '密码错误！'})
    else:  # 密码正确时，查询用户类型
        cur.execute("""select type from userinfo where username='%s'""" % username)
        usertype = cur.fetchone()
        session.clear()
        session['username'] = user[0]
        session['password'] = user[1]
        session['userID'] = user[2]
        session['usertype'] = user[3]
        if usertype[0] == 'admin':  # 根据用户类型跳转
            return jsonify({'status': 'ok', 'msg': '游乐园管理员登陆成功！', 'currentAuthority': usertype[0]})
        if usertype[0] == 'user':
            return jsonify({'status': 'ok', 'msg': '用户登陆成功！', 'currentAuthority': usertype[0]})


# 注册
@app.route('/register', methods=['POST'])
def registration():
    session.clear()
    data = json.loads(request.get_data(as_text=True))
    username = data['username']
    password = data['password']
    # email = data['email']
    usertype = 'user'
    if username is None or username == '':  # 检查用户名是否为空
        return jsonify({'status': 'error', 'msg': '用户名为空！'})
    else:
        sql = """select username from userinfo where username = '%s'""" % username
        cur.execute(sql)
        res = cur.fetchone()
        if res is not None:  # 若该用户名已被注册过，则提示账户名已存在
            return jsonify({'status':'error','msg':'用户名已存在！'})
        else:   # 若用户名没有重复
            if password is None or password == '': # 若密码为空
                return jsonify({'status': 'error', 'msg': '密码为空！'})
            else:   # 密码不为空，向数据库插入一条记录
                try:
                    sql = """insert into userinfo(username,password,type) values ('%s', '%s', '%s')""" %(username,password,usertype)
                    cur.execute(sql)
                    db.commit()  # 将获取的用户信息提交到数据库，userinfo表插入一条记录

                    cur.execute("""select userID from userinfo where username='%s'"""%username)
                    user = cur.fetchone()
                    session['userID'] = user[0]
                    return jsonify({'status': 'ok', 'msg': '注册成功！'})
                except Exception as e:
                    db.rollback()
                    return jsonify({'status': 'error', 'msg': '注册失败！'})


# 退出登录
@app.route('/logout',methods=['GET','POST'])
def logout():
    session.clear()
    return jsonify({'status':'ok','msg':'退出登录成功！'})


# 预订票
@app.route('/resevation',methods=['GET','POST'])
def reserve():
    userid = session.get('userID')
    if userid is None:
        return jsonify({'status':'error','msg':'用户未登录'})
    data = json.loads(request.get_data(as_text=True))
    itemName = data['itemname']   # 获取前端传回来的项目名称
    playdate = data['playdate']
    sql = """select * from item where itemName='%s' """%itemName # 查询相应项目的信息
    cur.execute(sql)
    item = cur.fetchone() # 存储查询的项目信息
    item = list(item)
    if item:
        # 通过itemID连表查询ticketnum表的余票信息
        cur.execute("""select leftNum from ticketnum,item 
        where ticketnum.itemID = item.itemID and item.itemID='%s'"""%item[0])
        ticket = cur.fetchone()
        if ticket[0]>=0:   # 若余票大于0，则可以进行购票
            #sql1 = """select * from userinfo where username='%s'"""%username
            cur.execute("""select * from userinfo where userID='%d'"""%userid)
            user = cur.fetchone()
            user = list(user)
            if user[4] >= item[3]:  # 判断用户余额是否足够买票
                user[4]-=item[3]
                try:  # 更新用户余额
                    sql = """update userinfo set money='%f' where userID='%d'"""%(user[4],userid)
                    cur.execute(sql)
                except Exception as e:
                    db.rollback()
                    return jsonify({'status':'error','msg':'更新用户余额失败','reason':e.__str__()})
                try:  # 生成一条购票的记录
                    sql = """insert into ticket(itemID,price,playdate,userID,reservetime,status) 
                    values ('%s','%s','%s','%d', now(),'%s')"""%(item[0],item[3],playdate,userid,'pending')
                    cur.execute(sql)
                except Exception as e:
                    db.rollback()
                    return jsonify({'status':'error','msg':'预订失败','reason':e.__str__()})
                try:  # 更新项目的余票信息
                    sql = """update ticketnum set leftnum=leftnum-1 where itemID='%s'""" % item[0]
                    cur.execute(sql)
                    db.commit()  # 如果以上sql语句执行都没有问题，则提交事务
                    return jsonify({'status': 'ok', 'msg': '预订成功'})
                except Exception as e:
                    db.rollback()
                    return jsonify({'status':'error','msg':'预订失败','reason':e.__str__()})

            else:
                return jsonify({'status':'error','msg':'余额不足不能购票'})
    else:
        return jsonify({'status':'error','msg':'找不到项目信息'})


# 修改用户名和密码
@app.route('/updateuser',methods=['GET','POST'])
def update_user():
    username = session.get('username')
    if username is None:
        return jsonify({'status':'error','msg':'用户未登录'})
    data = json.loads(request.get_data(as_text=True))
    newname = data['username']
    newpsd = data['password']
    if newname =='':
        return jsonify({'status':'error','msg':'用户名为空'})
    if newpsd == '':
        return jsonify({'status':'error','msg':'密码为空'})
    # 用户名密码都不为空，则查询用户名是否重复
    cur.execute("""select username from userinfo where username='%s'"""%newname)  # 查询名字是否重复
    res = cur.fetchone()
    if res:
        return jsonify({'status':'error','msg':'用户名重复'})
    try:
        cur.execute("""update userinfo set username='%s',password='%s'"""%(newname, newpsd))
        db.commit()
        return jsonify({'status':'ok','msg':'更新信息成功'})
    except Exception as e:
        db.rollback()
        return jsonify({'status':'error','msg':'更新信息失败','reason':e.__str__()})


# 取消预定
@app.route('/cancel', methods=['GET', 'POST'])
def cancel():
    pass


# 管理员添加项目信息
@app.route('/additem',methods=['GET','POST'])
def additem():
    if session.get('usertype') == 'admin':
        data = json.loads(request.get_data(as_text=True))
        itemname = data['itemname']
        itemdes = data['description']
        price = data['price']
        try:
            price = float(price)
        except Exception as e:
            return jsonify({'status':'error','msg':'数据类型不正确','reason':e.__str__()})
        if itemname == '':
            return jsonify({'status':'error','msg':'项目名称为空'})
        if itemdes == '':
            return jsonify({'status':'error','msg':'项目描述为空'})
        if price == '':
            return jsonify({'status':'error','msg':'项目价格为空'})
        try:
            cur.execute("""insert into item(itemname,itemdescription,price) values('%s','%s','%f')"""%(itemname,itemdes,price))
            db.commit()
            return jsonify({'status':'ok','msg':'添加项目成功'})
        except Exception as e:
            db.rollback()
            return jsonify({'status':'error','msg':'添加项目失败','reason':e.__str__()})








# web 服务器
if __name__ == '__main__':
    app.run('127.0.0.1', port=5000, debug=True)
