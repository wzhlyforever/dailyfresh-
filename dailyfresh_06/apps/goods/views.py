import json

from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage
from django.core.urlresolvers import reverse
from django.http import JsonResponse
from django.shortcuts import render, redirect

# Create your views here.
from django.template import loader
from django.views.generic import View

# 首页视图
from django_redis import get_redis_connection

from goods.models import GoodsCategory, IndexGoodsBanner, IndexPromotionBanner, IndexCategoryGoodsBanner, GoodsSKU


# 获取购物车数量 哪个视图需要就继承
class BaseCartView(View):
    # 获取购物车数量 哪个视图需要就继承
    def get_cart_num(self,request):
        cart_num = 0
        user = request.user  # user id 1 name： zhangsan   AnonymousUser
        # 购物车数据结构  登录后才能添加的  频繁访问存到redis
        if user.is_authenticated():
            # 每一个用户不一样 用redis的hash存储方便 cart_userid  ：  {'skuid1':'5','skuid2':'15','skuid3':'25'}
            # 获取购物车数量  每一个商品数量累加
            # 获取redis的链接实例
            redis_conn = get_redis_connection('default')

            # 获取购物车数据  得到一个字典  {'skuid1':'5','skuid2':'15','skuid3':'25'}
            cart = redis_conn.hgetall('cart_%s' % user.id)
        else:
            cart_json = request.COOKIES.get('cart')
            # 判断之前是否操作过购物车
            if cart_json is not None:
                cart = json.loads(cart_json)
            else:
                cart = {}

        # ['5','15','25']
        for value in cart.values():
            # 计算购物车所有的总量
            cart_num += int(value)

        return cart_num


class IndexView(BaseCartView):
    def get(self, request):

        # 先去缓存里拿数据 缓存里没有再去数据库查找
        context = cache.get('indexpage_static_cache')

        if context is None:
            print('缓存是空的')
            # 显示首页
            # 1.商品分类的全部数据
            categorys = GoodsCategory.objects.all()
            # 2。幻灯片
            banners = IndexGoodsBanner.objects.all().order_by('index')
            # 3.活动
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

            # 首页所有的分类的推荐数据    苹果 大虾 橘子 螃蟹 橙子
            # goodsbanners = IndexCategoryGoodsBanner.objects.all()

            #  循环所有的类别  [新鲜水果category ，海鲜category ，朱牛羊肉category]
            for category in categorys:
                # 查询对应类别下的数据 过滤条件category=category
                # display_type = 0查询的是显示文字的数据
                # display_type = 1查询的是显示图片的数据
                # order_by('index') 按照index排序 1234 小的在前

                # 鲜芒 加州提子 亚马逊牛油果 []
                title_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=0).order_by(
                    'index')
                # 把数据存到category的属性里
                category.title_banners = title_banners
                # 图片的数据
                image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1).order_by(
                    'index')
                # 把数据存到category的属性里
                category.image_banners = image_banners

            context = {
                'categorys': categorys,
                'banners': banners,
                'promotion_banners': promotion_banners,
            }

            # 多个用户可能数据相同 也有不相同， 把登录后的用的 相同的数据 保存到缓存 不用每次都去查找
            # 1key indexpage_static_cache  2value 无论保存的是什么 都会被转码成字符串 3有效期
            # 2 setting里的CACHES 就是设置的缓存的存储  这里存到了redis里
            # 3.过期时间 根据业务来定
            cache.set('indexpage_static_cache', context, 3600)
        else:
            print('使用的缓存的数据')

        # conten是数据渲染好的模板的最终html代码  文件流 异步 celery
        # content = loader.render_to_string('index.html', context)
        # print(content)

        # 获取购物车数量
        cart_num = self.get_cart_num(request)


        # 把数据添加到context
        context['cart_num'] = cart_num

        return render(request, 'index.html', context)


class DetailView(BaseCartView):
    """商品详细信息页面"""

    def get(self, request, sku_id):
        # 商品分类信息
        # 商品sku信息
        # 商品spu信息（商品详情和其他规格的sku）
        # 新品推荐
        # 评论信息
        # 如果登陆 查询购物车

        # 尝试获取缓存数据
        context = cache.get("detail_%s" % sku_id)

        # 如果缓存不存在
        if context is None:
            try:
                # 获取商品信息
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                # from django.http import Http404
                # raise Http404("商品不存在!")
                return redirect(reverse("goods:index"))

            # 获取类别
            categorys = GoodsCategory.objects.all()

            # 从订单中获取评论信息 一个商品 可能存在于多个订单 要全部查出来
            sku_orders = sku.ordergoods_set.all().order_by('-create_time')[:30]
            if sku_orders:
                for sku_order in sku_orders:
                    # datetime.strftime  格式化时间
                    sku_order.ctime = sku_order.create_time.strftime('%Y-%m-%d %H:%M:%S')
                    # 当前订单商品的用户名
                    sku_order.username = sku_order.order.user.username
            else:
                sku_orders = []

            # 获取最新推荐  当前类别的商品的前两个 按时间排序  大 -> 小
            new_skus = GoodsSKU.objects.filter(category=sku.category).order_by("-create_time")[:2]

            # 获取其他规格的商品  sku->spu>所有sku
            other_skus = sku.goods.goodssku_set.exclude(id=sku_id)

            context = {
                "categorys": categorys,
                "sku": sku,
                "orders": sku_orders,
                "new_skus": new_skus,
                "other_skus": other_skus
            }

            # 设置缓存
            cache.set("detail_%s" % sku_id, context, 3600)

        # 购物车数量
        cart_num = self.get_cart_num(request)
        # 如果是登录的用户
        if request.user.is_authenticated():
            # 获取用户
            user = request.user
            # 从redis中获取购物车信息
            redis_conn = get_redis_connection("default")
            # -------------------------------------------------------------
            # 商品添加到历史记录 ‘history_userid’: [sku1.id, sku2.id, sku3.id, sku4.id, sku5.id]
            # 把之前的相同的商品记录删掉
            # count>0   =0     <0
            redis_conn.lrem('history_%s' % user.id, 0, sku_id)

            # 当前商品添加到历史记录
            redis_conn.lpush('history_%s' % user.id, sku_id)

            # 只保存最多5条记录  ltrim截取前5个 其余的删了
            redis_conn.ltrim("history_%s" % user.id, 0, 4)

        # context.update({"cart_num": cart_num})
        context['cart_num'] = cart_num

        return render(request, 'detail.html', context)


class ListView(BaseCartView):
    #  当前类别   水果
    #  排序 default
    #  当前的页码  1
    # url的设计 restfull
    # http://127.0.0.1:8000/goods/list/categoryid/1?sort=price
    # url(r'^list/(?P<category_id>\d+)/(?P<page>\d+)$', views.ListView.as_view(), name='list'),
    def get(self, request, category_id, page):
        # 购物车
        # 当前类别
        # 所有的类别
        # 当前类别里所有的 商品
        # 新品推荐
        # 排序 默认default 价格price 人气hot
        # 分页的页码列表

        # 获取的排序
        sort = request.GET.get('sort')
        # 当前类别
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            # 没有这个类别 去主页 体验好
            return redirect(reverse('goods:index'))

        # 所有的类别
        categorys = GoodsCategory.objects.all()

        # 新品推荐
        new_skus = GoodsSKU.objects.filter(category=category).order_by("-create_time")[:2]

        # 默认default 价格price 人气hot
        if sort == 'price':
            skus = GoodsSKU.objects.filter(category=category).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(category=category).order_by('-sales')
        else:
            # 排序
            sort = 'default'
            # 所有的商品
            skus = GoodsSKU.objects.filter(category=category)

        # 分页  参1 所有商品 参2每页的数量
        paginator = Paginator(skus, 1)
        # [1,2,3,4,5,6,7,8,9]
        # 总页数 小于5页  num_pages<=5    paginator.page_range
        # 当前页page<=3   12345
        # 当前页在最后3页时  num_pages - page <=2
        # 其它

        # 转为int
        page = int(page)

        # 获取当前页的数据
        try:
            skus_page = paginator.page(page)
        except EmptyPage:
            # 如果没有这一页 就去第一页
            page = 1
            skus_page = paginator.page(page)

        # 获取页码列表  要写到 EmptyPage异常处理之后  page才是正确的数据
        if paginator.num_pages <= 5:
            page_list = paginator.page_range
        elif page <= 3:
            page_list = range(1, 6)
        elif paginator.num_pages - page <= 2:
            page_list = range(paginator.num_pages - 4, paginator.num_pages + 1)
        else:
            page_list = range(page - 2, page + 3)

        context = {
            'sort': sort,
            'category': category,
            'categorys': categorys,
            'new_skus': new_skus,
            'skus_page': skus_page,
            'page_list': page_list,
        }

        # 购物车数量
        cart_num = self.get_cart_num(request)

        context['cart_num'] = cart_num
        return render(request, 'list.html', context)
