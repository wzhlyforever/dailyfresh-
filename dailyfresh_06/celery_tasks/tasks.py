import os
# 添加环境变量
# os.environ["DJANGO_SETTINGS_MODULE"] = "dailyfresh_06.settings"
#
# # 放到Celery服务器上时添加的代码
# import django
# django.setup()


from celery import Celery
from django.conf import settings
from django.core.mail import send_mail

# 实例化Celery对象
# 参1：生成任务的文件路径  参2 broker的redis地址  redis://:密码@ip/数据库号
from django.template import loader

from goods.models import GoodsCategory, IndexGoodsBanner, IndexPromotionBanner, IndexCategoryGoodsBanner

app = Celery('celery_tasks.tasks',broker='redis://192.168.1.136:6379/3')

# 多进程 （cpu ）gevent greenlet

# 发送邮件的方法  装饰器 让方法成为celery的任务
@app.task
def send_active_email(recipient_list,user_name,token):
    # 126 163 qq

    html_body = '<h1>尊敬的用户 %s, 感谢您注册天天生鲜！</h1>' \
                '<br/><p>请点击此链接激活您的帐号<a href="http://127.0.0.1:8000/users/active/%s">' \
                'http://127.0.0.1:8000/users/active/%s</a></p>' % (user_name, token, token)
    # 参1 邮件标题
    # 参2 邮件的纯文本内容
    # 参3 谁发的
    # 参4 谁接收
    send_mail('天天生鲜激活', '', settings.EMAIL_FROM, recipient_list,html_message=html_body)

#生成主页的静态文件的方法
@app.task
def generate_static_index_html():
    # 1.商品分类的全部数据
    categorys = GoodsCategory.objects.all()
    # 2。幻灯片
    banners = IndexGoodsBanner.objects.all()
    # 3.活动
    promotion_banners = IndexPromotionBanner.objects.all()
    #  循环所有的类别  [新鲜水果category ，海鲜category ，朱牛羊肉category]
    for category in categorys:
        # 鲜芒 加州提子 亚马逊牛油果 []
        title_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=0).order_by('index')
        # 把数据存到category的属性里
        category.title_banners = title_banners
        # 图片的数据
        image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1).order_by('index')
        # 把数据存到category的属性里
        category.image_banners = image_banners
    context = {
        'categorys': categorys,
        'banners': banners,
        'promotion_banners': promotion_banners,
    }


    # conten是数据渲染好的模板的最终html代码  文件流 异步 celery
    # static_index是复制了一份index 删除了登录后相关的代码
    content = loader.render_to_string('static_index.html', context)
    # 把content保存成一个静态文件
    # 获取要写入的文件路径 存到static下叫index.html
    file_path = os.path.join(settings.STATICFILES_DIRS[0],'index.html')
    # 把数据写入文件
    with open(file_path,'w') as f:
        f.write(content)