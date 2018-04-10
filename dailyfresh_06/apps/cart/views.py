import json

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render, redirect

# Create your views here.
from django.views.generic import View

# 添加购物车
from django_redis import get_redis_connection

from goods.models import GoodsSKU


# 如果没有登录 也可以添加购物车
# 登录后 把之前的购物车的数据 添加到登录的账户里

# 登录后   cart_userid: {'skuid1':10,'skuid2':3 ....}

# 没登录  cart: '{'skuid1':10,'skuid2':3 ....}' json
# 存到cookie  在登录后 把数据转到服务器redis存到当前用户下

class AddCartView(View):
    def post(self, request):

        # 用户信息user
        # 应该接收的数据 skuid  数量count

        # 接收传来数据方法里的参数
        user = request.user

        # 需求后来让产品改了 不登录也能添加
        # if not user.is_authenticated():  # 必须登录后才能添加
        #
        #     return JsonResponse({'code': 5, 'msg': '用户没登录'})
        # 商品的skuid

        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 对数据校验(比如这个数据为空, 和这个数据乱传的清况, 通过判断和捕获异常的形式)
        if not all([sku_id, count]):
            return JsonResponse({'code': 1, 'msg': '参数不全'})

        # 验证商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'code': 2, 'msg': '商品不存在'})

        try:
            # 验证数量
            count = int(count)
        except Exception:
            return JsonResponse({'code': 3, 'msg': '数量不对'})

        # 数量不能超过库存
        if count > sku.stock:
            return JsonResponse({'code': 4, 'msg': '库存不足'})
        print(11111)
        # 如果用户登录 存到redis
        if user.is_authenticated():
            # 把数据存到redis   cart_userid: {'skuid1':10,'skuid2':3 ....}


            # 获取redis的链接实例
            # {b'skuid1': b'10', b'skuid2': b'3'....}
            redis_conn = get_redis_connection('default')
            # 判断当前的商品 是否已经存在于redis里

            # 获取商品之前的数量
            origin_count = redis_conn.hget('cart_%s' % user.id, sku_id)
            if origin_count is not None:
                # 已经存在 最后保存的数量 = 之前的数量+当前的数量
                # 注意redis里是string 要强转
                count += int(origin_count)
            # else:
            #     # 不存在   最后保存的数量 = 当前的数量
            # 保存到数据库
            redis_conn.hset('cart_%s' % user.id, sku_id, count)
        else:
            #  用户未登录 存到cookie中
            print(33)
            # 获取商品之前的数量
            # cart  ：  '{'skuid1':10,' skuid2':3 ....}'
            # 如果用户之前就没操作过购物车 获取的就是None
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                # 把字符串转为字典
                cart_dict = json.loads(cart_json)
            else:
                # 如果之前没操作过购物车 就生成一个空字典 方便后面使用
                cart_dict = {}
            print(sku_id)
            print(cart_dict)
            # 判断当前商品是否保存过
            if sku_id in cart_dict:
                print(3333)
                # 获取商品之前的数量
                origin_count = cart_dict.get(sku_id)
                count += origin_count

            # cart_dict :{'skuid1':10,' skuid2':3 ....}
            # 把添加后的数量 存到字典里
            print(222)
            cart_dict[sku_id] = count

        cart_num = 0
        # 如果登录 从redis查询购物车的数量
        if user.is_authenticated():
            # 查询购物车的数量
            # 获取用户
            user = request.user
            # 从redis中获取购物车信息
            redis_conn = get_redis_connection("default")
            # 如果redis中不存在，会返回None
            cart_dict = redis_conn.hgetall("cart_%s" % user.id)
            # else:
            # {'skuid1': 10, 'skuid2': 3....}
            # 没有登录 从cookie里获取  但是 获取的是旧的数据 新的数据已经在cart_dict里了
            # cart_json = request.COOKIES.get('cart')
            # cart_dict = json.loads(cart_json)
        print(3333)
        # 循环获取总的数量
        for val in cart_dict.values():
            cart_num += int(val)
        print(444)
        response = JsonResponse({'code': 0, 'msg': '添加购物车成功', 'cart_num': cart_num})
        print(555)
        print(cart_dict)
        if not user.is_authenticated():
            # 未登录 保存到cookie
            #  把字典转为字符串
            cart_json = json.dumps(cart_dict)
            # 保存到cookie中
            response.set_cookie('cart', cart_json)
        print(666)
        # {'code':3,'msg':'添加购物车失败'}   code 0 ：添加成功  代表状态码 一般0是成功
        return response


# 购物车信息页面
class CartInfoView(View):
    # 登录　在redis查数据
    # 没登录　cookie里查数据
    def get(self, request):
        user = request.user
        # 商品sku对象
        # 单个商品的数量
        # 单个商品的总价
        # 全部商品的数量
        # 全部商品的总价

        if user.is_authenticated():
            # 登录　在redis查数据
            redis_conn = get_redis_connection('default')
            # 获取所有的数据  {b'skuid1'：b'5', b'skuid2':b'10' }
            cart_dict = redis_conn.hgetall('cart_%s' % user.id)
        else:
            # 没登录　cookie里查数据
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart_dict = json.loads(cart_json)
            else:
                cart_dict = {}
            pass

        total_count = 0  # 全部商品的数量
        total_amount = 0  # 全部商品的总价
        skus = []  # 存放所有的sku对象
        # 遍历字典获取skuid 和数量
        for sku_id, count in cart_dict.items():
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                # 不管当前异常 继续获取下面的数据
                continue
            # 强转为数字 因为reids里存的是字符串
            count = int(count)  # 单个商品的数量
            amount = sku.price * count  # 单个商品的总价
            # 把商品的数量和总价 存到当前商品对象里
            sku.count = count
            sku.amount = amount
            total_count += count  # 全部商品的数量
            total_amount += amount  # 全部商品的总价
            skus.append(sku)  # 所有的sku对象

            # 对数据校验

        context = {
            'skus': skus,
            'total_count': total_count,
            'total_amount': total_amount,
        }

        return render(request, 'cart.html', context)


class UpdateCartView(View):
    def post(self, request):
        user = request.user
        # 更新的是哪个sku  skuid
        # 更新成多少数量 count
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 对数据校验
        if not all([sku_id, count]):
            return JsonResponse({'code': 1, 'msg': '参数不完整'})

        try:
            # 判断商品是否存在
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'code': 2, 'msg': '商品不存在'})

        try:
            count = int(count)
        except Exception:
            return JsonResponse({'code': 3, 'msg': '数量不正常'})

        # 判断是否超过库存
        if count > sku.stock:
            return JsonResponse({'code': 4, 'msg': '库存不足'})

        # 判断是否登录  来决定更改redis还是cookie的数据
        if user.is_authenticated():
            # 更改redis  {'id':10,'id2':30}
            redis_conn = get_redis_connection('default')
            # 更改sku_id商品的数量为新的数量count
            redis_conn.hset('cart_%s' % user.id, sku_id, count)
            return JsonResponse({'code': 0, 'msg': '更新购物车数量成功'})
        else:
            # 更改cookie
            # 取出所有的数据
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart_dict = json.loads(cart_json)
            else:
                cart_dict = {}
            # 把商品数据更新数量
            cart_dict[sku_id] = count

            response = JsonResponse({'code': 0, 'msg': '更新购物车数量成功'})
            # 注意存cookie 要把字典转换回json字符串
            response.set_cookie('cart', json.dumps(cart_dict))
            return response


class DeleteCartView(View):
    def post(self, request):
        user = request.user
        # 商品sku_id
        sku_id = request.POST.get('sku_id')

        # 校验
        if not sku_id:
            return JsonResponse({'code': 1, 'msg': '参数不对'})

        if user.is_authenticated():
            # {'id': 10, 'id2': 30}
            # 如果登录 从redis删除数据
            redis_conn = get_redis_connection('default')
            # 删除一个属性对应的数据
            redis_conn.hdel('cart_%s' % user.id, sku_id)
            return JsonResponse({'code': 0, 'msg': '删除成功'})
        else:
            # 没登录 从cookie删除数据
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                # 不是空的才能去删除
                cart_dict = json.loads(cart_json)
                # 如果id在字典里 就删除
                if sku_id in cart_dict:
                    del cart_dict[sku_id]
                    response = JsonResponse({'code': 0, 'msg': '删除成功'})
                    # 注意存cookie 要把字典转回json字符串
                    response.set_cookie('cart', json.dumps(cart_dict))
                    return response

        return JsonResponse({'code': 0, 'msg': '删除成功'})
