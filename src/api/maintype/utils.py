
import random
import sys
import importlib.util
import os
import traceback
from types import ModuleType
from typing import NoReturn, Union
import tempfile
import platform
import ctypes
import struct

def random_str(length:int=8, words="1234567890abcdef")->str:
    '''生成随机字符串
    '''
    ret = ''
    for i in range(length):
        index = random.randint(0, len(words)-1)
        ret += words[index]
    return ret

def random_bytes(length:int=8)->bytes:
    '''生成随机字节流
    '''
    ret = b''
    for i in range(length):
        ret += struct.pack('B', random.randint(0, 255))
    return ret

def print_traceback()->NoReturn:
    '''输出堆栈信息
    '''
    traceback.print_exc()

def load_module_from_bytes(code:bytes)->Union[ModuleType, None]:
    '''从字节流加载Python模块
    '''
    fd, fpath = tempfile.mkstemp()
    with open(fpath, 'wb') as f:
        f.write(code)
    m = load_module(fpath)
    os.unlink(fpath)
    return m

def load_module(path: str)->Union[ModuleType, None]:
    '''加载指定位置处的Python模块
    '''
    def load(file_path:str, name:str)->Union[ModuleType, None]:
        sepc = importlib.util.spec_from_file_location(name, file_path)
        if sepc is None:
            return None
        module:Union[ModuleType, None] = importlib.util.module_from_spec(sepc)
        old = sys.modules.get(name)
        if name is not None:
            sys.modules[name] = module
        try:
            sepc.loader.exec_module(module)
        except BaseException as e:
            raise e
            module = None
        if name is not None:
            if old:
                sys.modules[name] = old
            else:
                sys.modules.pop(name)
        return module

    if os.path.isdir(path):# 如果是目录则当做Python包加载
        name = os.path.basename(path)
        path = os.path.join(path, '__init__.py')
        if not os.path.isfile(path):
            return None
        else:
            return load(path, name)
    elif os.path.isfile(path) and path.lower().endswith(".py"):
        name, ext = os.path.splitext(os.path.basename(path))
        return load(path, name)
    else:
        return None

def get_current_shell_type()->str:
    '''获取当前终端类型
    '''
    types = ['sh', 'bash', 'ash', 'zsh', 'dash', 'powershell', 'cmd', 'other']
    if platform.platform().lower().startswith('win'):
        if os.environ.get('PROMPT') and os.environ.get('COLUMNS') is None:
            return 'cmd'
        else:
            return 'powershell'
    else:
        sh = os.path.split(os.environ.get('SHELL'))[1].lower()
        if sh in types:
            return sh
        else:
            return 'other'

def call_path(floor=1)-> str:
    '''返回调用该函数时指定层数的文件绝对路径,默认返回调用该函数时所在的文件路径

    :params floor: 指定调用该函数时调用栈的层序数（从最低层1开始），将会返回该层的文件路径.
    :returns: 返回指定调用栈所在的文件绝对路径
    '''
    stack = traceback.extract_stack()
    return os.path.abspath(stack[-floor-1].filename)

def file_get_content(fpath:str)->Union[bytes, None]:
    '''获取指定文件的内容

    :params fpath: 一个系统中的文件路径
    :returns: 返回文件内容的字节流，失败返回None
    '''
    if not os.path.isfile(fpath):
        return None
    with open(fpath, 'rb') as f:
        return f.read()

def file_set_content(fpath:str, content:bytes)->Union[int, None]:
    '''向指定文件路径写入字节流内容

    :params fpath: 一个系统中的文件路径，若存在多级目录不存在则写入会失败
    :params content: 向文件写入的字节流内容
    :returns: 返回写入的字节数，失败返回None
    '''
    try:
        with open(fpath, 'wb') as f:
            return f.write(content)
    except:
        return None

def getbytes(echo=False, read_ctrl_seq=True)-> bytes:
    """获取一次按键产生的字节

    Args:
        echo (bool, optional): 是否回显输入. Defaults to False.
        read_ctrl_seq (bool, optional): 是否一次读取完整控制序列. Defaults to True.

    Returns:
        bytes: 返回一次按键产生的字节
    """
    ch = b''
    if 'linux' in platform.platform().lower():
        termios = importlib.import_module('termios')
        # 获取标准输入的描述符
        fd = sys.stdin.fileno()

        # 获取标准输入(终端)的设置
        old_ttyinfo = termios.tcgetattr(fd)

        # 配置终端
        new_ttyinfo = old_ttyinfo[:]

        # 使用非规范模式(索引3是c_lflag 也就是本地模式)
        new_ttyinfo[3] &= ~termios.ICANON
        # 关闭回显(输入不会被显示)
        if not echo:
            new_ttyinfo[3] &= ~termios.ECHO

        # 使设置生效
        termios.tcsetattr(fd, termios.TCSANOW, new_ttyinfo)
        # 从终端读取
        ch = os.read(fd, 20 if read_ctrl_seq else 1)

        # 还原终端设置
        termios.tcsetattr(fd, termios.TCSANOW, old_ttyinfo)
    else:
        # Windows终端
        msvcrt = importlib.import_module('msvcrt')
        func = msvcrt.getch
        if echo:
            func = msvcrt.getche
        ch = func()
        if ch in (b'\x00', b'\xe0') and read_ctrl_seq:
            ch += func()

    return ch

def kill_thread(threadid: int) -> bool:
    """杀死指定的线程

    Args:
        threadid (int): 线程ID

    Returns:
        bool: 成功返回True，失败返回False
    """
    tid = ctypes.c_long(threadid)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        tid, ctypes.py_object(SystemExit))
    if res != 1:
        return False
    return True

def del_note_1(code:bytes)->bytes:
    '''删除//和/**/的注释 
    '''
    quotes = b"'\"`"
    length = len(code)
    end = 0
    result = b''
    quote = None
    while end<length:
        if code[end:end+1] in quotes:
            if quote is None:
                quote = code[end:end+1]
            elif quote == code[end:end+1]:
                quote = None
        elif quote is None and code[end:end+1] == b'/' and end<length-1:
            end += 1
            tmp = code[end:end+1]
            if tmp in b'/*':
                end += 1
                while end < length:
                    if code[end:end+1] == b'\n' and tmp == b'/': # 单行注释
                        end += 1
                        break
                    elif code[end:end+1] == b'*' and tmp == b'*' and end < length-1: # 多行注释
                        end += 1
                        if code[end:end+1] == b'/':
                            end += 1
                            break
                    end += 1
            else:
                result += b'/'+tmp
                end += 1
            continue
        result += code[end:end+1]
        end += 1
    return result


def edit_on_editor(data:bytes, editor:str, filename='tempfile')->Union[bytes, None]:
    """在编辑器中编辑传入数据

    Args:
        data (bytes): 要编辑的数据字节流
        editor (str): 编辑器路径或命令
        filename (str): 编辑器显示的文件名称

    Returns:
        Union[bytes, None]: 编辑后的数据字节流, 若编辑器打开失败则返回None
    """
    fname = filename.replace('/', '_').replace('\\', '_')
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, fname)
        with open(path, 'wb') as f:
            f.write(data)
        if os.system(f"{editor} {path}") != 0:
            return None

        with open(path, 'rb') as f:
            return f.read()