from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import classonlymethod


# 用来验证是否登录的类 需要就继承
class LoginRequiredMixin(object):
    @classonlymethod
    def as_view(cls, **initkwargs):
        # 调用父类的as_view
        view = super().as_view(**initkwargs)
        return login_required(view)


# 定义一个装饰器 用来装饰视图函数 判断是否登录 如果没有登录返回json数据
def Login_Required_Json(view_func):
    @wraps(view_func) #恢复view_func的名字和文档
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated():
            return view_func(request, *args, **kwargs)
        else:
            return JsonResponse({'code':1, 'msg': '用户未登录'})

    return wrapper


# 用来验证是否登录的类 需要就继承
class LoginRequiredJsonMixin(object):
    @classonlymethod
    def as_view(cls, **initkwargs):
        # 调用父类的as_view
        view = super().as_view(**initkwargs)
        return Login_Required_Json(view)

#用来添加事务的类 需要的继承
class TransactionAtomicMixin(object):
    @classonlymethod
    def as_view(cls, **initkwargs):
        # 调用父类的as_view
        view = super().as_view(**initkwargs)
        return transaction.atomic(view)
