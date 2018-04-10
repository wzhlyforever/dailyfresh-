import json

from django.core.paginator import Paginator, EmptyPage
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect

# Create your views here.
from django.utils import timezone
from django.views.generic import View
from django_redis import get_redis_connection

from goods.models import GoodsSKU
from orders.models import OrderInfo, OrderGoods
from users.models import Address
from utils.views import LoginRequiredMixin, LoginRequiredJsonMixin, TransactionAtomicMixin


class PlaceOrdereView(View):
    def post(self, request):

        user = request.user

        # 前段页面要传输 数据

        # 1购物车点击提交过来  传过来 sku_ids
        # 2详情页面点击立即购买 传过来sku_ids 和count

        # 注意 id有多个传过来获取要用getlist 如果用get只能获取到最后一个
        sku_ids = request.POST.getlist('sku_ids')
        # 只有从详情页面点击立即购买 才会传count
        count = request.POST.get('count')

        # 下面的逻辑最后再写
        # 如果用没有登录 重定向到登录页面
        # 如果是从详情页过来的 那么就保存到cookie里数据
        if not user.is_authenticated():
            response = redirect('/users/login?next=/cart')
            # 用户没有登录
            if count is not None:
                # 取出cookie里的数据
                cart_json = request.COOKIES.get('cart')
                # 如果cookie里有数据
                if cart_json:
                    cart_dict = json.loads(cart_json)
                else:
                    cart_dict = {}
                # {'id1':5,'id2':7}
                # 从立即购买页面进来 只有一个商品 取第0个
                sku_id = sku_ids[0]
                # 添加到字典里
                cart_dict[sku_id] = int(count)
                # 从定向到购物车
                if cart_dict:
                    response.set_cookie('cart', json.dumps(cart_dict))
            return response
        # 上面的逻辑最后再写


        # 校验参数
        if sku_ids is None:
            # 产品说的算 要进购物车 从立即购买过来的
            return redirect(reverse('cart:info'))

        # 收货地址 有user能查到
        # 获取商品的sku对象 skus
        # 每种商品的数量
        # 每种商品的数量总价
        # 所有的商品的数量
        # 所有的商品的总价
        # 运费10
        # 所有的商品的总价包括运费

        # 1收货地址 取最新的一个
        try:
            address = Address.objects.filter(user=user).latest('create_time')
        except:
            # 没有就是空 让用户去编辑
            address = None
        skus = []
        total_count = 0  # 所有的商品的数量
        total_sku_amount = 0  # 所有的商品的总价
        total_amount = 0  # 所有的商品的总价 包括运费
        trans_cost = 10  # 运费
        redis_conn = get_redis_connection('default')
        # {b'skuid1':b'10',b'skuid2':b'15'}
        cart_dict = redis_conn.hgetall('cart_%s' % user.id)
        if count is None:
            # 从购物车过来的
            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # 产品说的算 要进购物车
                    return redirect(reverse('cart:info'))
                # 注意sku_id要转换为字节型才能获取
                sku_count = cart_dict.get(sku_id.encode())
                sku_count = int(sku_count)  # 每种商品的数量
                sku_amount = sku_count * sku.price  # 每种商品的总价
                # 把信息存到sku对象里
                sku.count = sku_count
                sku.amount = sku_amount
                # 保存全部的sku
                skus.append(sku)
                total_count += sku_count  # 所有的商品的数量
                total_sku_amount += sku_amount  # 所有的商品的总价
        else:
            # 从详情页点击立刻购买过来的   # 查商品数据
            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # 产品说的算 要进购物车
                    return redirect(reverse('cart:info'))
                # 强转数量
                try:
                    sku_count = int(count)  # 每种商品的数量
                    # href='{%url  'goods:detail'  1%}'
                    # http: // 127.0.0.1: 8000 / goods / detail / 12
                except Exception:
                    return redirect(reverse('goods:detail', args=sku_id))
                # 判断库存
                if sku_count > sku.stock:
                    return redirect(reverse('goods:detail', args=sku_id))
                sku_amount = sku_count * sku.price  # 每种商品的总价
                # 把数据存到sku对象里
                sku.count = sku_count
                sku.amount = sku_amount
                # 保存全部的sku
                skus.append(sku)
                total_count += sku_count  # 所有的商品的数量
                total_sku_amount += sku_amount  # 所有的商品的总价
                # 把当前商品加入到购物车字典里
                cart_dict[sku_id] = sku_count

            # 把商品加入到购物车
            # 1可以在提交订单的时候 不管从哪个页面进来都可以查询数量
            # 2.如果用户把页面关掉 可以从购物车查询到
            if cart_dict:
                redis_conn.hmset('cart_%s' % user.id, cart_dict)

        # 所有的商品的总价 包括运费
        total_amount = total_sku_amount + trans_cost

        context = {
            'skus': skus,
            'total_count': total_count,
            'total_sku_amount': total_sku_amount,
            'total_amount': total_amount,
            'trans_cost': trans_cost,
            'address': address,
            'sku_ids':','.join(sku_ids)  #[1,2,3,4,5]  '1,2,3,4,5'
        }
        # 返回订单信息页面 注意还没有生成 提交后才生成
        return render(request, 'place_order.html', context)


# 提交订单的视图  用户有没有登录
class CommitOrderView(LoginRequiredJsonMixin, TransactionAtomicMixin, View):
    # 有大量数据传过来 用于生成订单 用post ajax请求

    def post(self, request):
        # 接收的参数  # user 地址id 支付方式 商品id  数量
        user = request.user
        address_id = request.POST.get('address_id')  # 地址id
        pay_method = request.POST.get('pay_method')  # 支付方式
        # 前段ajax无法直接传过来数组列表 所以传过来一个字符串  '1, 2, 3, 4, 6'
        sku_ids = request.POST.get('sku_ids')  # 商品id  '1, 2, 3, 4, 6' split [1,2,3,5,6]

        # 校验参数
        if not all([address_id, pay_method, sku_ids]):
            return JsonResponse({'code': 1, 'msg': '参数不完整'})

        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return JsonResponse({'code': 2, 'msg': '地址不存在'})

        if pay_method not in OrderInfo.PAY_METHOD:
            return JsonResponse({'code': 3, 'msg': '支付方式错误'})

        redis_conn = get_redis_connection('default')
        # {b'skuid1':b'1',b'skuid2':b'7'....}
        redis_dict = redis_conn.hgetall('cart_%s' % user.id)

        # 订单号规则 20180315155959+userid
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 生成一个保存点 回滚用
        save_point = transaction.savepoint()

        # 创建订单数据 存到订单表里
        # 注意这里生成订单时 还没有计算商品的总数量和总价格 后面再去添加 save一次
        try:
            order = OrderInfo.objects.create(
                order_id=order_id,  # 订单号
                user=user,  # 用户
                address=address,  # 地址
                total_amount=0,  # 总价格
                trans_cost=10,  # 运费
                pay_method=pay_method,  # 支付方式
            )
            total_count = 0  # 订单全部商品的总数量
            total_amount = 0  # 订单全部商品的总价格
            # 分割得到一个列表
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                for i in range(3):
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        # 有异常 订单就不需要了 回滚 到save_point
                        transaction.savepoint_rollback(save_point)
                        return JsonResponse({'code': 4, 'msg': '商品不存在'})
                    # 不要忘记encode转为字节类型
                    sku_count = redis_dict.get(sku_id.encode())  # 获取当前商品的数量
                    # 强转
                    sku_count = int(sku_count)
                    # 判断库存
                    if sku_count > sku.stock:
                        # 有异常 订单就不需要了 回滚 到save_point
                        transaction.savepoint_rollback(save_point)
                        return JsonResponse({'code': 5, 'msg': '库存不足'})

                    # 当前真实库存 和之前的库存对比
                    # 保存之前查出来的库存
                    origin_stock = sku.stock  # 总量10个当前已经被a买走了5个 但是b之前查到的库存依然是10
                    new_stock = origin_stock - sku_count
                    new_sales = sku.sales + sku_count

                    # 更新成功 返回影响的行数 当前只有一个商品 成功返回1 不成功是0
                    result = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).\
                        update(stock=new_stock, sales=new_sales)
                    # 10 5   5  3
                    if result == 0 and i<2:
                        # 给三次机会去数据库查库存
                        continue
                    elif result == 0 and i ==2:
                        # 第3次依然不成功 给用户一个响应  回滚
                        transaction.savepoint_rollback(save_point)
                        return JsonResponse({'code':6, 'msg': '生成订单失败'})

                    break

                # # 减少sku库存sku_count
                # sku.stock -= sku_count
                # # 增加sku销量sku_count
                # sku.sales += sku_count

                # 当前商品总价
                sku_amount = sku_count * sku.price

                total_count += sku_count  # 订单总数量
                total_amount += sku_amount  # 订单总价

                # 保存一个商品数据到订单商品表OrderGoods
                OrderGoods.objects.create(
                    order=order,  # 当前商品属于的订单
                    sku=sku,  # 当前商品
                    count=sku_count,  # 当前商品的数量
                    price=sku_amount,  # 当前商品总价
                )

            # 把订单总数量和总价格 添加进数据库
            order.total_amount = total_amount + 10
            order.total_count = total_count
            order.save()
        except Exception:
            # 有异常 订单就不需要了 回滚 到save_point
            transaction.savepoint_rollback(save_point)
            return JsonResponse({'code': 6, 'msg': '生成订单失败'})

        # 事务提交
        transaction.savepoint_commit(save_point)

        # 订单生成后删除购物车(hdel) 注意*sku_ids 解包
        redis_conn.hdel('cart_%s' % user.id, *sku_ids)
        # 后端 只负责订单生成
        # 成功或者失败 要去做什么 由前端来做
        return JsonResponse({'code': 0, 'msg': '提交成功'})


#我的订单
class UserOrdersView(LoginRequiredMixin, View):
    """用户订单页面"""
    def get(self, request, page):
        user = request.user
        # 查询当前用户所有订单
        orders = user.orderinfo_set.all().order_by("-create_time")

        for order in orders:
            # 通过字典把数字对应的汉字取出来 存到对象里
            order.status_name = OrderInfo.ORDER_STATUS[order.status]
            order.pay_method_name = OrderInfo.PAY_METHODS[order.pay_method]
            order.skus = []
            order_skus = order.ordergoods_set.all()
            for order_sku in order_skus:
                sku = order_sku.sku
                sku.count = order_sku.count
                sku.amount = sku.price * sku.count
                order.skus.append(sku)
        # 分页
        page = int(page)
        try:
            paginator = Paginator(orders, 3)
            page_orders = paginator.page(page)
        except EmptyPage:
            # 如果传入的页数不存在，就默认给第1页
            page_orders = paginator.page(1)
            page = 1
        # 页数
        page_list = paginator.page_range

        context = {
            "orders": page_orders,
            "page": page,
            "page_list": page_list,
        }

        return render(request, "user_center_order.html", context)