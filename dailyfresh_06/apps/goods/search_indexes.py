from haystack import indexes
from goods.models import GoodsSKU

# GoodsSKUIndex  模型类名Index
"""建立索引时被使用的类"""
class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
     # text是索引字段名   一般通用叫text   use_template 使用模板来指定表里哪写字段需要添加索引
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        """从哪个表中查询"""
        return GoodsSKU

    def index_queryset(self, using=None):
        """返回要建立索引的数据"""
        return self.get_model().objects.all()