from api import utils, logger, Session
import json
import base64
import threading
import os
import importlib
import sys
import time

from api.maintype.info import OSType

class BaseShell:
    r'''基本的交互式shell，输入一条命令并获取结果， 每次命令执行都是独立的
    '''
    def __init__(self, session:Session):
        self.session = session
        self.running = False

    def cmdloop(self):
        logger.info("简单的命令执行模式.键入 `exit` 或 `Ctrl-C` 来退出.")
        logger.warning("这个shell只是简单的命令循环执行，并非交互式的shell，要使用具有交互式的shell请使用`normal`或`namedpipe`类型")
        self.running = True
        try:
            while self.running:
                cmd = input(">> ")
                if cmd:
                    if cmd.lower() == 'exit':
                        self.running = False
                        break
                    msg = self.session.exec(cmd.encode()+b" 2>&1")
                    if msg is None:
                        logger.error(f"执行 `{cmd}` 失败!")
                        continue
                    print(msg.decode(self.session.options.get_option('encoding').value, 'ignore'))
        except KeyboardInterrupt:
            pass

class NormalShell(BaseShell):
    r'''通过文件维持交互式shell的输入输出，需要webshell能够执行命令且能控制命令的输入输出流
    '''
    def __init__(self, session:Session, shell: str):
        super().__init__(session)

        self.shell = shell

        self.out_file = self.session.server_info.tmpdir + self.session.server_info.sep + utils.random_str(8)+"_out"
        self.in_file = self.session.server_info.tmpdir + self.session.server_info.sep + utils.random_str(8)+"_in"
        self._lock = threading.Lock()
        self._verbose = 0

        self.last_recv = '' # 上次接收到的数据
    
    def close(self):# 清理生成的临时文件，使shell退出
        self._lock.acquire()
        if self.running:
            self.session.evalfile("interact_normal/close", dict(pwd=self.session.server_info.pwd, infile=self.in_file, outfile=self.out_file))
            logger.info("shell已经退出!")
            self.running = False
        self._lock.release()
    
    def writer(self, cmd: str):
        self._lock.acquire()
        self.last_recv = None # 写入命令前将上次接收内容置空
        self._lock.release()
        ret = self.session.evalfile("interact_normal/writer", dict(cmd=cmd, pwd=self.session.server_info.pwd, infile=self.in_file))
        if ret is None:
            logger.error(f"写入命令`{cmd}`失败!")
            return
        if ret == b"-1":
            self.close()
    
    def reader(self):
        while self.running:
            ret = self.session.evalfile("interact_normal/reader", dict(pwd=self.session.server_info.pwd, outfile=self.out_file), 0)
            if ret is None:
                continue
            ret = json.loads(ret)
            if ret['code'] == -1:
                break
            elif ret['code'] == 1:
                msg = base64.b64decode(ret['msg'].encode()).decode(self.session.options.get_option('encoding').value, 'ignore')
                self._lock.acquire()
                self.last_recv = msg
                self._lock.release()
                print(msg, end="", flush=True)
        self.close()
    
    def start_shell(self):
        ret = self.session.evalfile("interact_normal/shell", dict(shell=self.shell, pwd=self.session.server_info.pwd, infile=self.in_file, outfile=self.out_file), 0)
        if ret is None:
            logger.warning("请求`start_shell`已经退出, 如果shell仍正常运行请忽略该警告")
            return
        if ret == "-1":
            logger.error("无法运行shell，远程服务器缺少必要的运行库!")
        elif ret == "-2":
            logger.error("交互式shell进程开启失败!")
        self.close()
    
    def cmdloop(self):
        self.running = True
        start_thread = threading.Thread(target=self.start_shell)
        reader_thread = threading.Thread(target=self.reader)
        thread_list = [start_thread, reader_thread]
        start_thread.setDaemon(True)
        reader_thread.setDaemon(True)
        start_thread.start()
        time.sleep(1)
        reader_thread.start()

        try:
            if self.session.server_info.os_type == OSType.UNIX and self._is_supported_shell():
                logger.info('你能键入`:getfshell`来升级成一个完全交互式shell(前提是你已经获得了一个pty)')
                logger.info("键入`Ctrl + c`三次来退出完全交互式shell")
            while self.running:
                cmd = input()
                if not cmd:
                    continue
                if self.session.server_info.os_type == OSType.UNIX and cmd == ':getfshell' and self._is_supported_shell():
                    if not self.enter_fully_shell():
                        logger.error("无法获得一个完全交互式shell")
                        continue
                    break
                self.writer(cmd+'\n')
        except KeyboardInterrupt:
            pass
        except BaseException as e:
            logger.error(e)
        
        self.close()
        for t in thread_list:
            t.join(5)
            if t.is_alive():
                utils.kill_thread(t.ident)

    def _is_supported_shell(self)-> bool:
        '''判断当前终端是否支持完全交互式shell
        '''
        if utils.get_current_shell_type() not in ('cmd', 'powershell', 'other'):
            return True
        return False

    def enter_fully_shell(self)-> bool:
        '''获取完全交互式shell，仅支持Unix（服务器和本机）,需要首先获取一个tty
        '''
        self.writer('tty && echo -e "ok\\tok" || echo -e "not\\ta\\ttty"\n')
        msg = ''
        sign = False
        while True:
            self._lock.acquire()
            msg = self.last_recv
            self._lock.release()
            if msg is not None:
                if "not\ta\ttty" in msg:
                    logger.error("当前未获得一个pty!")
                    break
                elif "ok\tok" in msg:
                    sign = True
                    break
            if not self.running:
                return False
            time.sleep(0.1)
        if sign:
            rows = os.get_terminal_size().lines
            columns = os.get_terminal_size().columns
            term = os.environ.get('TERM', 'linux')
            self.writer(f'export TERM={term};export SHELL=bash;stty rows {rows} columns {columns}\n')
            # 设置当前terminal
            termios = importlib.import_module('termios')
            tty = importlib.import_module('tty')
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            new = old[:]
            new[3] &= ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, new)
            tty.setraw(fd, termios.TCSANOW)
            logger.info("现在你已进入一个完全交互式shell!", True)

            # 进入完全交互式shell
            exit_code = b''
            while self.running:
                cmd = utils.getbytes()
                if cmd == b"\x03":
                    exit_code += b'\x03'
                else:
                    exit_code = b''
                if exit_code == b'\x03\x03\x03':
                    break
                self.writer(cmd)

            # 还原终端设置
            termios.tcsetattr(fd, termios.TCSANOW, old)
            return True
        return False