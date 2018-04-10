import json
import re

import itsdangerous
from django import db
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils.decorators import classonlymethod
from django.views.generic import View

# Create your views here.

# 注册模块
# def register(request):
#     # 展示页面 get
#     # 注册  post
#     if request.method == 'GET':
#         return render(request, 'register.html')
#     else:
#         # 执行注册逻辑
#
#         return HttpResponse('okpost')



# 注册的类视图

# 1 django提供了各种功能的类视图可以继承  ListVIew DetailView FormView
# 2如果不能满足需求 继承View 自己去写
# 3每种请求分开 结构清晰
from celery_tasks.tasks import send_active_email
from goods.models import GoodsSKU
from users.models import User, Address
from utils.views import LoginRequiredMixin


class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    # 执行注册逻辑
    def post(self, request):
        # 1获取传过来的数据
        username = request.POST.get('user_name')  # 用户名
        psw = request.POST.get('pwd')  # 密码
        email = request.POST.get('email')  # 邮件
        allow = request.POST.get('allow')  # 同意协议

        # 2校验数据
        # 判断是否为空
        if not all([username, psw, email]):
            return redirect(reverse('users:register'))

        # 判断邮箱格式
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式错误'})

        # checkbox如果勾选 后穿过来一个on
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '没有同意协议'})


            # 3执行注册逻辑
            # 保存到数据库 insert
        # user = User()
        # user.username = username
        # user.password = psw
        # user.save() #insert
        # 密码加密  123456 + jfdsldsfjldsfjldsjk+当前时间  加盐值 混淆
        try:
            user = User.objects.create_user(username=username, email=email, password=psw)
        except db.IntegrityError:
            return render(request, 'register.html', {'errmsg': '用户已经注册'})
        # django默认是激活的 不符合需求 改为不激活
        user.is_active = False
        # 保存到数据库 insert
        user.save()

        # 生成token  包含user.id  生成token的过程 叫签名
        token = user.generate_active_token()

        # 给用户发送激活邮件

        # 接收邮件的人 可以有多个
        # recipient_list = [user.email] 应该发给user.email
        #  为了测试方便 就写固定了了
        recipient_list = ['itheima_test@163.com']  # user.email

        # 发送邮件的方法  发邮件是耗时的  处理图片 音视频 需要异步执行
        # 通过delay调用 通知work执行任务
        send_active_email.delay(recipient_list, user.username, token)

        # 5给浏览器响应
        return HttpResponse('注册成功，请去激活')


from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from django.conf import settings


# http://127.0.0.1:8000/users/active/fjdldskgerjg;lrdjgl;kdfmkdmk;lajf;lkasjdf;lkas
class ActiveView(View):
    def get(self, request, token):
        # 解析token 获取用户id数据
        # 参1 混淆用的盐  参2 过期时间
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            result = serializer.loads(token)  # {"confirm": self.id}
        except itsdangerous.SignatureExpired:
            return HttpResponse('激活邮件已过期')

        userid = result.get('confirm')

        # 根据id获取用户
        try:
            uesr = User.objects.get(id=userid)
        except User.DoesNotExist:
            return HttpResponse('用户不存在')

        # if uesr.is_active:
        #     return HttpResponse('用户已经激活')

        # 激活用户
        uesr.is_active = True
        uesr.save()  # update

        return redirect(reverse('users:login'))


class LoginView(View):
    # 返回登录页面
    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        # 接收数据
        username = request.POST.get('username')
        psw = request.POST.get('pwd')
        print(username)
        print(psw)
        # 校验数据
        if not all([username, psw]):
            return redirect(reverse('users:login'))

        # 数据库获取用户

        # 数据库的密码是加密的
        # psw = sha256（psw）
        # User.objects.filter(username = username,password=psw)

        # django提供的验证方法 成功返回user对象 不成功返回none

        user = authenticate(username=username, password=psw)
        if user is None:
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})

        # 判断是否激活
        if not user.is_active:
            # print(1111)
            return render(request, 'login.html', {'errmsg': '用户未激活'})

        # django提供的 用来保存用户信息 到session里 实现比如十天不用登录等功能
        login(request, user)

        # 获取是否记住用户
        remembered = request.POST.get('remembered')

        # session 存到redis

        # session  默认None 2周  0 关闭 浏览器就没有  具体时间比如1000s
        if remembered != 'on':
            # 没有记住用户
            request.session.set_expiry(0)
        else:
            # 2周有效期
            request.session.set_expiry(None)

        # 合并购物车  要求:
        # 在登录跳转前 ,合并redis和cookie购物车上商品数量信息
        # 如果cookie中存在的，redis中也有，则进行数量累加
        # 如果cookie中存在的，redis中没有，则生成新的购物车数据
        # 合并完后 清除cookie里的购物车数据

        # 1获取cookie里的数据
        cart_json = request.COOKIES.get('cart')
        if cart_json is not None:
            cart_dict_cookie = json.loads(cart_json)
        else:
            cart_dict_cookie = {}

        # 2获取redis里的数据
        redis_conn = get_redis_connection('default')
        cart_dict_redis = redis_conn.hgetall('cart_%s' % user.id)
        print(cart_json)  # {"4": 3, "1": 2}
        print(cart_dict_redis)  # {b'8': b'3', b'1': b'13', b'5': b'10', b'6': b'1', b'2': b'4'}
        # 遍历所有的cookie里的数据
        for sku_id, count in cart_dict_cookie.items():
            # 因为redis里的数据全部是字节类型 判断时要把cookie里的id转化为字节
            sku_id = sku_id.encode()  # "1" > b'1'
            # 判断cookie里的商品是否在redis里
            if sku_id in cart_dict_redis:
                # redis里的数量
                origin_count = cart_dict_redis[sku_id]
                count += int(origin_count)
            # 数据存到redis字典里
            cart_dict_redis[sku_id] = count

        # cart_dict_redis {}
        # mset cart_1
        # 字典数据存到redis  注意 cart_dict_redis不能是空字典
        if cart_dict_redis:
            redis_conn.hmset('cart_%s' % user.id, cart_dict_redis)

        # 如果之前是去用户相关的页面 而重定向到登录页面的
        # 那么登录以后就跳转到用户相关的界面
        # http://127.0.0.1:8000/users/login?next=/users/address
        # next=/users/address  根据是否有next来确定
        next = request.GET.get('next')
        if next is None:
            # 去商品主页
            response = redirect(reverse('goods:index'))
        else:
            # # http: // 127.0.0.1: 8000 / users / login?next = / orders / place
            # if next == '/orders/place':
            #     # 去订单页面 但是订单页接收的是post请求和数据
            #     response = redirect(reverse('cart:info'))
            # else:
            # 冲顶向到用户相关页面
            response = redirect(next)
        # 删除cookie里的购物车数据
        response.delete_cookie('cart')
        return response


# 登出功能
class LogoutView(View):
    def get(self, request):
        # 清除登录信息
        # 登出功能
        logout(request)

        return redirect(reverse('users:login'))


# 收货地址
class AddressView(LoginRequiredMixin, View):
    def get(self, request):
        # 用户是否登录
        # request有一个user对象
        # 如果用户登录后 就是用户的User对象
        # 如果没有登录  user不是None 是AnonymousUser 的对象 里面没有用户信息

        # user = request.user
        # if not user.is_authenticated():
        #         # 没有登录 去登录页面
        #     return render(request,'login.html')

        user = request.user
        # Address.objects.filter(user=user)
        # 排序获取最近添加的地址
        # user.address_set.order_by('-create_time')[0]

        # 排序获取最近添加的地址 只会返回一个值
        try:
            address = user.address_set.latest('create_time')
        except Address.DoesNotExist:
            # 没有获取到地址
            address = None

        context = {
            # 'user':user,  uesr不用传模板里有可以直接使用
            "address": address
        }
        return render(request, 'user_center_site.html', context)

    def post(self, request):
        """修改地址信息"""
        user = request.user
        # 获取地址信息
        recv_name = request.POST.get("recv_name")
        addr = request.POST.get("addr")
        zip_code = request.POST.get("zip_code")
        recv_mobile = request.POST.get("recv_mobile")
        # 判断不为空
        if all([recv_name, addr, zip_code, recv_mobile]):
            # address = Address(
            #     user=user,
            #     receiver_name=recv_name,
            #     detail_addr=addr,
            #     zip_code=zip_code,
            #     receiver_mobile=recv_mobile
            # )
            # address.save()

            # 创建好一个地址信息 保存到数据库 insert
            Address.objects.create(
                user=user,
                receiver_name=recv_name,
                detail_addr=addr,
                zip_code=zip_code,
                receiver_mobile=recv_mobile
            )

        return redirect(reverse("users:address"))


from django_redis import get_redis_connection


# 用户信息页面
class UserInfoView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user

        # 排序获取最近添加的地址 只会返回一个值
        try:
            address = request.user.address_set.latest('create_time')
        except Address.DoesNotExist:
            # 没有获取到地址
            address = None

        # 获取浏览记录
        # 存在redis  string 列表 集合 有序集合 hash   key-value

        # 列表  lpush  rpush
        # 存的是  ‘history_userid’ : [sku1.id,sku2.id,sku3.id,sku4.id,sku5.id]
        # 获取redis的链接实例
        redis_conn = get_redis_connection('default')
        # 获取数据  lrange 0 4   得到前5个商品id列表  []
        sku_ids = redis_conn.lrange('history_%s' % user.id, 0, 4)

        # 去数据库查询具体数据
        # select * from dfgoodssku where id in
        # skus = GoodsSKU.objects.filter(id__in = sku_ids)
        # redis [8,3,6,4,2,5,7]   mysql  [2,3,4,5,6]            [8,3,6,4,2]
        skus = []
        for sku_id in sku_ids:
            # 查询每一个sku
            sku = GoodsSKU.objects.get(id=sku_id)
            # 添加到列表里
            skus.append(sku)

        context = {
            "address": address,
            'skus': skus,
        }
        return render(request, 'user_center_info.html', context)
