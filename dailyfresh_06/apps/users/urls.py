
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth.decorators import login_required

from users import views





urlpatterns = [
    url(r'^register$', views.RegisterView.as_view() ,name='register'),#注册
    url(r'^active/(?P<token>.+)$', views.ActiveView.as_view() ,name='active'),#激活
    url(r'^login$', views.LoginView.as_view() ,name='login'),#登录
    url(r'^logout$', views.LogoutView.as_view() ,name='logout'),#登出

    # 直接作为方法使用 装饰器  把视图函数传进来
    # url(r'^address$', login_required(views.AddressView.as_view()) ,name='address'),#收货地址
    url(r'^address$', views.AddressView.as_view() ,name='address'),#收货地址
    url(r'^info$', views.UserInfoView.as_view() ,name='info'),#用户信息
]
