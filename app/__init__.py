from flask import Flask, redirect, json, jsonify
from flask import request, session
from flask.templating import render_template
import pymysql
from datetime import timedelta
import os

# 打开数据库连接
db = pymysql.connect(host='127.0.0.1', user='root', password='123456', db='dbap1')
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
    sql = """select * from project where projectName='%s' """%itemName  # 查询相应项目的信息
    cur.execute(sql)
    project = cur.fetchone() # 存储查询的项目信息
    project = list(project)
    if project:
        # 通过projectID连表查询用户选择的游玩日期当天的余票信息
        cur.execute("""select leftNum from project_ticket,project 
        where project.projectID = project_ticket.projectID and project.projectID='%s'"""%project[0])
        ticket = cur.fetchone()
        if ticket[0]>=0:   # 若余票大于0，则可以进行购票
            #sql1 = """select * from userinfo where username='%s'"""%username
            cur.execute("""select * from userinfo where userID='%d'"""%userid)
            user = cur.fetchone()
            user = list(user)
            if user[4] >= project[3]:  # 判断用户余额是否足够买票
                user[4]-=project[3]
                try:  # 更新用户余额
                    sql = """update userinfo set money='%f' where userID='%d'"""%(user[4],userid)
                    cur.execute(sql)
                except Exception as e:
                    db.rollback()
                    return jsonify({'status':'error','msg':'更新用户余额失败','reason':e.__str__()})
                try:  # 生成一条购票的记录
                    sql = """insert into record(projectID,playdate,userID,reservetime,status) 
                    values ('%d','%s','%s', now(),'%s')"""%(project[0],playdate,userid,'pending')
                    cur.execute(sql)
                except Exception as e:
                    db.rollback()
                    return jsonify({'status':'error','msg':'预订失败','reason':e.__str__()})
                try:  # 更新项目的余票信息
                    sql = """update project_ticket set leftnum=leftnum-1 where projectID='%d'""" % project[0]
                    cur.execute(sql)
                    db.commit()  # 如果以上sql语句执行都没有问题，则提交事务
                    return jsonify({'status': 'ok', 'msg': '预订成功'})
                except Exception as e:
                    db.rollback()
                    return jsonify({'status':'error','msg':'预订失败','reason':e.__str__()})

            else:
                return jsonify({'status':'error','msg':'余额不足不能购票'})
        else:
            return jsonify({'status':'error','msg':'余票不足不能购票'})
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
    username = session.get('username')
    if username is None:
        return jsonify({'status':'error','msg':'用户未登录'})
    data = json.loads(request.get_data(as_text=True))
    ticketID = data['ticketID']
    ticketID = int(ticketID)
    cur.execute("""select * from record where ticketID='%d'"""%ticketID)
    ticket = cur.fetchone()  # 获取用户的购票信息
    if not ticket:
        return jsonify({'status':'error','msg':'找不到购票信息'})
    sql = """select project_ticket.projectID from project_ticket,record 
    where project_ticket.projectID=record.projectID and ticketID='%d' and project_ticket.date=record.playdate"""%ticketID
    cur.execute(sql) # 根据票的信息查找对应日期的项目
    projcetID = cur.fetchone()
    if not projcetID:
        return jsonify({'status':'error','msg':'找不到对应的项目'})
    try:  # 更新剩余票数
        cur.execute("""update project_ticket set leftNum=leftNum+1 where projectID='%d'"""%projcetID[0])
    except Exception as e:
        return jsonify({'status':'error','msg':'更新余票失败','reason':e.__str__()})
    try:
        cur.execute("""select * from userinfo where username='%s'"""%username)
        user = cur.fetchone() # 查询的用户信息
        cur.execute("""select price from project where projectID='%d'"""%projcetID[0])
        price = cur.fetchone() # 查询票价
        money = user[4]+price[0] # 更新用户的余额
        money = float(money)
        cur.execute("""update userinfo set money='%f' where username='%s' """%(money,username))
    except Exception as e:
        return jsonify({'status':'error','msg':'更新用户余额失败','reason':e.__str__()})
    try:  # 删除购票记录
        cur.execute("""delete from record where ticketID='%d'"""%ticketID)
        db.commit()
        return jsonify({'status':'ok','msg':'取消预订成功'})
    except Exception as e:
        db.rollback()
        return jsonify({'status':'error','msg':'删除购票信息失败','reason':e.__str__()})



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
            cur.execute("""insert into project(projectname,projectdescription,price) values('%s','%s','%f')"""%(itemname,itemdes,price))
            db.commit()
            return jsonify({'status':'ok','msg':'添加项目成功'})
        except Exception as e:
            db.rollback()
            return jsonify({'status':'error','msg':'添加项目失败','reason':e.__str__()})
    elif session.get('usertype') == 'user':
        return jsonify({"status":'error','msg':'普通用户无权访问'})
    elif session.get('usertype') != 'user' or session.get('usertype') == 'admin':
        return jsonify({'status':'error','msg':'用户类型错误'})
    else:
        return jsonify({'status':'error','msg':'未登录'})


#删除项目
@app.route('/drop_item', methods=['GET', 'POST'])
def drop_item():
    userid = session.get('userID')
    if userid is None:
        return jsonify({'status': 'error', 'msg': '用户未登录'})
    sql="""select * from userinfo where userID='%d'""" % userid
    cur.execute(sql)
    user=cur.fetchone()
    user=list(user)
    if user[3]=='admin':
        data = json.loads(request.get_data(as_text=True))
        itemID = data['itemID']  # 获取前端传回来的票据ID
        itemID = int(itemID)
        sql = """select * from project where projectID='%d' """ % itemID  # 查询相应票据的信息
        cur.execute(sql)
        item = cur.fetchone()  # 存储查询的票据信息
        item = list(item)
        if item:
            sql="""select * from record where projectID='%d' and status='pending'""" %item[0]
            cur.execute(sql)
            user1=cur.fetchone()
            if user1 is None:
                try:
                    sql="""delete from project where projectID='%d'""" % item[0]
                    cur.execute(sql)
                    db.commit()
                    return jsonify({'status': 'ok', 'msg': '删除项目成功!'})
                except Exception as e:
                    db.rollback()
                    return jsonify({'status': 'error', 'msg': '删除项目失败', 'reason': e.__str__()})
            else:
                return jsonify({'status': 'ok', 'msg': "该项目有预定的未使用的票，无法进行删除！"})

        else:
            return jsonify({'status': 'ok', 'msg': "项目不存在，无法进行删除！"})
    else:
        return jsonify({'status': 'ok', 'msg': "您没有管理员权限，无法使用删除项目功能！"})


#查询项目
@app.route('/query_item', methods=['GET', 'POST'])
def query_item():
    userid = session.get('userID')
    if userid is None:
        return jsonify({'status': 'error', 'msg': '用户未登录'})
    data = json.loads(request.get_data(as_text=True))
    itemID = data['itemID']
    itemID = int(itemID)
    sql="""select * from project where projectID='%d'"""  % itemID
    cur.execute(sql)
    item=cur.fetchone()
    if item:
        return jsonify({'status':'ok','msg':'查询项目信息成功','data':item})
    else:
        return jsonify({'status': 'error', 'msg': '项目不存在，无法查询'})







# web 服务器
if __name__ == '__main__':
    app.run('127.0.0.1', port=5000, debug=True)
