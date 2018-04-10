from django.conf import settings
from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client


class FastDFSStorage(Storage):
    def _open(self):
        # 访问文件的时候
        pass

    def __init__(self, client_conf=None, server_ip=None):
        if client_conf is None:
            # 如果使用者 没有传 就使用默认的配置文件
            client_conf = settings.FDFS_CLIENT

        self.client_conf = client_conf

        if server_ip is None:
            server_ip = settings.SERVER_IP
        self.server_ip = server_ip

    # name 是图片的原始的名字  content是图片对象 读取文件用content.read()
    def _save(self, name, content):
        # 存储图片会走的方法

        # 把图片存到fastdfs

        # 生成fdfs客户端对象 用来访问fdfs服务器
        client = Fdfs_client(self.client_conf)
        # 读取图片二进制信息
        file_data = content.read()
        # 上传到fastdfs
        try:
            # 上传的过程中 是远程连接 也可能出现异常
            ret = client.upload_by_buffer(file_data)
        except Exception as e:
            print(e)
            # 异常抛出去 让调用人员也能处理
            raise

        # {
        #     'Group name': 'group1',
        #     'Status': 'Upload successed.',  # 注意这有一个点
        #     'Remote file_id': 'group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.py',
        #     'Uploaded size': '6.0KB',
        #     'Local file name': 'test',
        #     'Storage IP': '192.168.243.133'
        # }

        if ret.get('Status') == 'Upload successed.':  # TODO注意这有一个点
            # 判断是否上传成功
            # 获取文件的真实路径和名字
            file_id = ret.get('Remote file_id')
            return file_id
        else:
            # 抛出异常让调用人员 自己捕获处理
            raise Exception('上传图片到fdfs出现问题了')

    # 由于Djnago不存储图片，所以永远返回Fasle，直接引导到Fastdfs
    def exists(self, name):
        return False

    # 返回能够访问到图片的地址
    def url(self, name):

        # name :/group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.py
        # http://192.168.1.136:8888/group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.py

        # < img src = "{{ sku.default_image.url}}" >

        return self.server_ip + name

