from src.api.wrapper import Wrapper
from src.api.plugin import Plugin
from src.api.session import Session
from src.api.executor import CodeExecutor, CommandExecutor
from src.api.ui.logger import logger
import src.api.maintype.utils as utils
import os, sys
from typing import Callable, Dict, List, Type, Tuple, Union


__all__ = ['plugin_manager']

class DefaultWrapper(Plugin, Wrapper):
    '''默认的payload包装器，不做处理的返回输入payload
    '''
    name = 'DefaultWrapper'
    description = 'This is the default payload wrapper and will not do anything with the payload'
    help_info = 'This is the default payload wrapper and will not do anything with the payload'
    plugin_id = 'default_wrapper'

    def wrap(self, payload: bytes) -> bytes:
        return payload
    
    def on_loading(self, session: Session) -> bool:
        return True

class PluginManager:
    '''管理所有插件
    '''

    def __init__(self):
        self.__plugin_map:Dict[str, Type[Plugin]] = {} # 插件字典，键为ID，值为Plugin派生类

    def load_all_plugins(self, plugin_dirs:List[str])->int:
        """递归加载给定插件目录下的所有插件

        步骤：
            1.递归扫描插件目录
            2.若是Python文件，则尝试加载
            3.若是Python包，则尝试加载
            4.若是普通目录，则当做插件目录回到第一步
            5.若是普通文件或缓存目录，则略过

        Args:
            plugin_dirs (List[str]): 插件目录列表，每一项为一个插件目录地址

        Returns:
            int: 返回加载成功的数量
        """
        win = 0

        def recursion_load(plugin_dir:str, basename:str)->int:
            w = 0
            if not os.path.isdir(plugin_dir):
                return w
            for d in os.listdir(plugin_dir):# 插件目录加载
                plugin_path = os.path.join(plugin_dir, d)
                if d == '__pycache__' or (os.path.isfile(plugin_path) and not d.endswith('.py')): # 跳过缓存目录和普通文件
                    continue
                if os.path.isdir(plugin_path) and '__init__.py' not in os.listdir(plugin_path): # 若是普通目录则当做插件目录加载
                    w += recursion_load(plugin_path, basename+'/'+d)
                    continue
                if self.load_plugin(plugin_path, basename):
                    w += 1

            return w

        for plugin_dir in plugin_dirs:
            if not os.path.isdir(plugin_dir):
                continue
            win += recursion_load(plugin_dir, os.path.basename(plugin_dir))
        
        self.__plugin_map['__default_wrapper'] = DefaultWrapper # 默认的payload包装器插件
        DefaultWrapper
        win += 1
        return win

    def load_plugin(self, path:str, basename:str)->bool:
        """从指定路径加载插件

        每个插件应该都是一个Python模块，插件加载过程如下：
            1. 判断是否为一个python模块，是则进行下一步
            2. 判断该模块是否导出了一个名为get_plugin_class的函数，有则进行下一步
            3. 尝试无参调用该包的get_plugin_class函数，若发生异常则加载失败，否则保存返回值进行下一步
            4. 若返回值为一个Plugin的派生类则加载成功，否则加载失败

        Args:
            path (str): 一个合法的路径字符串
            basename (str): 当前插件的简短路径，用于生成插件ID

        Returns:
            bool: 加载成功返回True，失败返回False
        """
        func_name = 'get_plugin_class'
        path = os.path.abspath(path)
        module = utils.load_module(path)
        if not module:
            logger.error(f"加载插件`{path}`失败，这不是一个Python模块!")
            return False
        if not hasattr(module, func_name):
            logger.error(f"加载插件`{path}`失败，未定义`{func_name}`函数!")
            return False
        get_plugin_class:Callable[[], Type[Plugin]] = getattr(module, func_name)
        try:
            plugin_class = get_plugin_class()
            if not issubclass(plugin_class, Plugin):
                logger.error(f"加载插件`{path}`失败，导出的不是一个Plugin派生类!")
                return False
        except BaseException as e:
            logger.error(f"加载插件`{path}`失败，产生了异常：{e}!")
            return False
        else:
            ID = basename+'/'+os.path.splitext(os.path.basename(path))[0]
            if ID in self.__plugin_map:
                raise Exception(f"加载插件`{path}`出现了同名ID`{ID}`")
            self.__plugin_map[ID] = plugin_class
            plugin_class.plugin_id = ID
        return True

    def remove(self, ID:str)->Plugin:
        return self.__plugin_map.pop(ID)

    def get_plugin(self, ID:str, type=Plugin):
        '''获取指定ID的插件实例
        '''
        plugin = self.__plugin_map.get(ID)
        if plugin and issubclass(plugin, type):
            return plugin()
        return None

    def get_command_executor(self, ID:str)->CommandExecutor:
        '''获取CommandExecutor插件实例, 失败返回None
        '''
        return self.get_plugin(ID, CommandExecutor)

    def get_code_executor(self, ID:str)->CodeExecutor:
        '''获取代码执行器插件实例, 失败返回None
        '''
        return self.get_plugin(ID, CodeExecutor)

    def get_wrapper(self, ID:str)->Wrapper:
        '''获取包装器插件实例, 失败返回None
        '''
        return self.get_plugin(ID, Wrapper)

    def get_default_wrapper(self)->DefaultWrapper:
        '''获取一个默认的payload包装器实例
        '''
        return DefaultWrapper()

    def get_plugin_id(self, plugin:Plugin)->Union[str, None]:
        '''根据插件实例获取插件对应的ID

        :params plugin: 需要查找ID的插件实例
        :returns: 返回插件实例对应的插件ID，失败返回None
        '''
        for ID, p in self.__plugin_map.items():
            if plugin.__class__ == p:
                return ID
        return None

    def get_plugin_list(self, type:Type[object]=Plugin)->list:
        '''获取指定类型的插件列表

        :param type:要查找的类型
        :returns: 返回指定类型的插件列表
        '''
        ret = []
        for plugin_class in self.__plugin_map.values():
            if issubclass(plugin_class, type):
                ret.append(plugin_class)
        return ret

    @property
    def plugins_map(self)->Dict[str, Type[Plugin]]:
        return self.__plugin_map.copy()


plugin_manager = PluginManager()
