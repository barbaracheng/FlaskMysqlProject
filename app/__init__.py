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
        projectname = data['projectname']
        projectdes = data['description']
        price = data['price']
        try:
            price = float(price)
        except Exception as e:
            return jsonify({'status':'error','msg':'数据类型不正确','reason':e.__str__()})
        if projectname == '':
            return jsonify({'status':'error','msg':'项目名称为空'})
        if projectdes == '':
            return jsonify({'status':'error','msg':'项目描述为空'})
        if price == '':
            return jsonify({'status':'error','msg':'项目价格为空'})
        cur.execute("""select projectName from project where projectName='%s'""" % projectname)
        if cur.fetchone() is not None:
            return jsonify({'status': 'error', 'msg': '项目名称重复'})
        try:
            cur.execute("""insert into project(projectname,projectdescription,price) values('%s','%s','%f')"""%(projectname,projectdes,price))
            db.commit()
            return jsonify({'status':'ok','msg':'添加项目成功'})
        except Exception as e:
            db.rollback()
            return jsonify({'status':'error','msg':'添加项目失败','reason':e.__str__()})
    elif session.get('usertype') == 'user':
        return jsonify({"status":'error','msg':'普通用户无权访问'})
    elif session.get('usertype') != 'user' or session.get('usertype') != 'admin':
        return jsonify({'status':'error','msg':'用户类型错误'})
    else:
        return jsonify({'status':'error','msg':'未登录'})


# 删除项目
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
        projectID = data['projectID']  # 获取前端传回来的项目ID
        projectID = int(projectID)
        sql = """select * from project where projectID='%d' """ % projectID  # 查询相应项目的信息
        cur.execute(sql)
        item = cur.fetchone()  # 存储查询的项目信息
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


# 查询项目
@app.route('/query_item', methods=['GET', 'POST'])
def query_item():
    userid = session.get('userID')
    if userid is None:
        return jsonify({'status': 'error', 'msg': '用户未登录'})
    data = json.loads(request.get_data(as_text=True))
    prjectID = data['projectID']
    try:
        prjectID = int(prjectID)
    except Exception as e:
        return jsonify({'status':'error','msg':'数据类型不正确','reason':e.__str__()})
    sql="""select * from project where projectID='%d'"""  % prjectID
    cur.execute(sql)
    item=cur.fetchone()
    if item:
        return jsonify({'status':'ok','msg':'查询项目信息成功','projectID':item[0],
                        'projectName':item[1],'projectDescription':item[2],'price':item[3]})
    else:
        return jsonify({'status': 'error', 'msg': '项目不存在，无法查询'})


# 查询个人信息
@app.route('/personal_info',methods=['GET'])
def personal_info():
    username = session.get('username')
    if username is None:
        return jsonify({'status':'error','msg':'用户未登录'})
    cur.execute("""select * from userinfo where username='%s'"""%username)
    user = cur.fetchone()
    if user is None:
        return jsonify({'status':'error','msg':'找不到该用户信息'})
    return jsonify({'status':'ok','msg':'查询成功','username':user[0],'userID':user[2],'usertype':user[3],'money':user[4],'email':user[5]})


# 添加门票信息
@app.route('/add_ticket',methods=['GET','POST'])
def add_ticket():
    username = session.get('username')
    if username is None:
        return jsonify({'status':'error','msg':'用户未登录'})
    cur.execute("""select type from userinfo where username='%s'"""%username)
    usertype = cur.fetchone()
    if usertype[0] == 'admin':
        data = json.loads(request.get_data(as_text=True))
        projectName = data['projectname']
        date = data['date']
        total_num = data['totalNum']
        total_num = int(total_num)
        if date == '' or date is None:
            return jsonify({'status':'error','msg':'日期不能为空'})
        if total_num == '' or total_num is None:
            return jsonify({'status':'error','msg':'总票数不能为空'})
        # 查询项目表中是否有对应的项目ID
        cur.execute("""select project.projectID from project,project_ticket 
                where project.projectID=project_ticket.projectID and projectName='%s'""" % projectName)
        projectID = cur.fetchone()
        if projectID is None:
            return jsonify({'status':'error','msg':'没有对应的项目，不能添加门票信息'})
        cur.execute("""select date from project_ticket where date='%s' """%date)
        res = cur.fetchone()
        if res:
            return jsonify({'status':'error','msg':'该项目当天的门票已经存在了'})
        try:
            cur.execute("""insert into project_ticket(projectID,date,totalNum,leftNum)
             values('%d','%s','%d','%d')"""%(projectID[0],date,total_num,total_num))
            db.commit()
            return jsonify({'status':'ok','msg':'添加门票信息成功','projectID':projectID[0],'date':date,'total_num':total_num,'left_num':total_num})
        except Exception as e:
            db.rollback()
            return jsonify({'status':'error','msg':'添加门票失败','reason':e.__str__()})
    else:
        return jsonify({'status':'error','msg':'您不是管理员，没有该权限'})


# 修改项目门票信息
@app.route('/update_pro',methods=['GET','POST'])
def update_pro():
    username = session.get('username')
    if username is None:
        return jsonify({'status': 'error', 'msg': '用户未登录'})
    cur.execute("""select type from userinfo where username='%s'"""%username)
    usertype = cur.fetchone()
    if usertype[0] == 'admin':
        data = json.loads(request.get_data(as_text=True))
        projectID = data['projectID']
        try:
            projectID = int(projectID)
        except Exception as e:
            return jsonify({'status':'error','msg':'数据类型不正确','reason':e.__str__()})
        date = data['date']
        totalnum = data['totalnum']
        try:
            totalnum = int(totalnum)
        except Exception as e:
            return jsonify({'status': 'error', 'msg': '数据类型不正确', 'reason': e.__str__()})
        count = cur.execute("""select date from record,project_ticket where 
        date=playdate and project_ticket.projectID=record.projectID 
        and date='%s' and record.projectID='%d' and status='%s'"""%(date,projectID,'pending'))
        #return jsonify({'1':totalnum,'2':totalnum-count})
        try:
            cur.execute("""update project_ticket set totalNum='%d',leftNum='%d' 
            where projectID='%d' and date='%s'"""%(totalnum,totalnum-count,projectID,date))
            #cur.execute("""update project_ticket set leftNum='%d' where projectID='%d' and date='%s'"""%(totalnum-count,projectID,date))
            db.commit()
            return jsonify({'status':'ok','msg':'修改项目门票信息成功'})
        except Exception as e:
            db.rollback()
            return jsonify({'status':'error','msg':'修改项目门票失败','reason':e.__str__()})
    else:
        return jsonify({'status':'error','msg':'不是管理员，没有该权限'})


# 显示所有项目
@app.route('/display_project',methods=['GET'])
def display_project():
    username = session.get('username')
    if username is None:
        return jsonify({'status': 'error', 'msg': '用户未登录'})
    cur.execute("""select type from userinfo where username='%s'"""%username)
    usertype = cur.fetchone()
    if usertype[0] == 'admin':
        count = cur.execute("""select project.projectID,projectName,projectDescription,price,date,
        totalNum,leftNum from project,project_ticket where project.projectID=project_ticket.projectID""")
        res = cur.fetchall()
        result = []
        for i in range(count):
            temp={}
            temp['projectID'] = res[i][0]
            temp['projectName'] = res[i][1]
            temp['projectDescripton'] = res[i][2]
            temp['price'] = res[i][3]
            temp['date'] = res[i][4]
            temp['totalNum'] = res[i][5]
            temp['leftNum'] = res[i][6]
            result.append(temp)
        return jsonify({'status':'ok','msg':'查询所有项目成功','data':result})
    #cur.execute("""select * from project,project_ticket where """)


# 显示用户购票记录
@app.route('/user_record',methods=['GET'])
def display_record():
    username = session.get('username')
    if username is None:
        return jsonify({'status': 'error', 'msg': '用户未登录'})
    count = cur.execute("""select ticketID,projectName,playdate,userID,reservetime,status
     from record,project where record.projectID=project.projectID and username='%s'"""%username)
    record = cur.fetchall()
    record_list=[]
    for i in range(count):
        temp = {}
        temp['ticketID'] = record[i][0]
        temp['projectName'] = record[i][1]
        temp['playdate'] = record[i][2]
        temp['userID'] = record[i][3]
        temp['reservetime'] = record[i][4]
        temp['status'] = record[i][5]
        record_list.append(temp)
    return jsonify({'status':'ok','msg':'查询个人购票信息成功','data':record_list})



# 显示所有购票记录
@app.route('/display_record',methods=['GET'])
def display_user_record():
    username = session.get('username')
    if username is None:
        return jsonify({'status': 'error', 'msg': '用户未登录'})
    cur.execute("""select type from userinfo where username='%s'"""%username)
    usertype = cur.fetchone()
    if usertype == 'admin':
        count = cur.execute("""select * from record""")
        records = cur.fetchall()
        records_list = []
        for i in range(count):
            temp = []
            temp['ticketID'] = records[i][0]
            temp['projectID'] = records[i][1]
            temp['playdate'] = records[i][2]
            temp['userID'] = records[i][3]
            temp['reservetime'] = records[i][4]
            temp['status'] = records[i][5]
            records_list.append(temp)
        return jsonify({'status':'ok','msg':'查询所有购票记录成功','data':records_list})
    else:
        return jsonify({'status':'error','msg':'您不是管理员，没有该权限'})


# web 服务器
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
