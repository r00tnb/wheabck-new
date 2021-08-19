import os
import sys
import importlib

# 程序名称
app_name = "wheabck"

# src路径
src_path = os.path.dirname(__file__)

# 根路径
root_path = os.path.dirname(src_path)

# api路径
api_path = os.path.join(src_path, 'api')
sys.modules['api'] = importlib.import_module('.api', 'src')

# 插件路径
plugins_path = os.path.join(root_path, 'plugins')

# 命令历史文件
history_path = os.path.join(root_path, '.cmd_history')

#########################################################
# 数据库相关
#########################################################
# 数据库路径
db_path = os.path.join(root_path, 'wheabck.db')

