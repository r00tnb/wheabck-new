import threading
import json
import base64
import importlib
import os
import sys
import time
from api import utils, logger
from api.maintype.info import OSType
from api.session import Session
from .base import BaseShell

class NamedpipeUnixShell(BaseShell):
    r'''使用管道通信生成一个交互式shell，用于类Unix系统
    '''
    def __init__(self, session:Session, shell: str):
        super().__init__(session)
        self.shell = shell

        self.out_pipe = self.session.server_info.tmpdir+self.session.server_info.sep+utils.random_str(10)+"_out" # 输出管道，结果会写入该管道
        self.in_pipe = self.session.server_info.tmpdir+self.session.server_info.sep+utils.random_str(10)+"_in" # 输入管道，命令会从该管道读取

        self._lock = threading.Lock()
        self.last_recv = None

    def close(self):
        self._lock.acquire()
        if self.running:
            self.session.evalfile('interact_namedpipe/unix/close', dict(outpipe=self.out_pipe, inpipe=self.in_pipe, pwd=self.session.server_info.pwd),5)
            self.running = False
            logger.info("shell已经退出!")
        self._lock.release()

    def _shell(self):# 服务端执行shell
        self.session.exec(f"{self.shell} >{self.out_pipe} 2>&1 <{self.in_pipe}".encode()) # 阻塞
        self.close()

    def _keep_shell_alive(self):# 连接到管道保持shell一直存活
        self.session.exec(f"mkfifo {self.in_pipe} {self.out_pipe} && chmod 777 {self.in_pipe} {self.out_pipe}") # 先尝试使用命令创建管道
        ret = self.session.evalfile('interact_namedpipe/unix/keep', dict(outpipe=self.out_pipe, inpipe=self.in_pipe, pwd=self.session.server_info.pwd),0)
        if ret is None:
            logger.error("`Keep_shell_alive`错误!")
        elif ret == "-1":
            logger.info("`posix_mkfifo`创建命名管道失败!")
        self.close()

    def _reader(self):# 从管道读取结果
        while(self.running):
            ret = self.session.evalfile('interact_namedpipe/unix/reader', dict(outpipe=self.out_pipe, pwd=self.session.server_info.pwd),0)
            if ret is None:
                logger.error("读取错误!")
                continue
            ret = json.loads(ret)
            if ret['code'] == 1:
                data = base64.b64decode(ret['msg'].encode()).decode(self.session.options.get_option('encoding'), 'ignore')
                self._lock.acquire()
                self.last_recv = data
                self._lock.release()
                print(data, end="", flush=True)
            elif ret['code'] == -2:
                continue
            elif ret['code'] == -1:
                self.close()
                break
        logger.info("读取线程退出")

    def _writer(self, cmd:str):# 写入一个命令
        self._lock.acquire()
        self.last_recv = None # 写入命令前将上次接收内容置空
        self._lock.release()
        ret = self.session.evalfile('interact_namedpipe/unix/writer', dict(cmd=cmd, inpipe=self.in_pipe, pwd=self.session.server_info.pwd))
        if ret is None:
            logger.error(f"命令`{cmd}`写入失败!")
        elif ret == "-1":
            self.close()

    def cmdloop(self):
        self.running = True
        thread_list = []
        keepthread = threading.Thread(target=self._keep_shell_alive, name="keep shell alive")
        shellthread = threading.Thread(target=self._shell, name="shell")
        readerthread = threading.Thread(target=self._reader, name="reader")
        keepthread.setDaemon(True)
        shellthread.setDaemon(True)
        readerthread.setDaemon(True)

        thread_list.append(keepthread)
        keepthread.start()
        time.sleep(1)
        if self.running:
            thread_list.append(shellthread)
            thread_list.append(readerthread)
            shellthread.start()
        else:
            return

        time.sleep(1)
        readerthread.start()
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
                self._writer(cmd+'\n')
        except KeyboardInterrupt:
            pass

        self.close()
        logger.info("等待线程退出...")
        for t in thread_list:
            t.join(5)
            if t.is_alive() and not utils.kill_thread(t.ident):
                logger.error(f"退出线程`{t.name}`失败, 线程ID是`{t.ident}`!")
        logger.info("线程清理完毕!")

    def _is_supported_shell(self)-> bool:
        '''判断当前终端是否支持完全交互式shell
        '''
        if utils.get_current_shell_type() not in ('cmd', 'powershell', 'other'):
            return True
        return False

    def enter_fully_shell(self)-> bool:
        '''获取完全交互式shell，仅支持Unix（服务器和本机）,需要首先获取一个tty
        '''
        self._writer('tty && echo -e "ok\\tok" || echo -e "not\\ta\\ttty"\n')
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
            self._writer(f'export TERM={term};export SHELL=bash;stty rows {rows} columns {columns}\n')
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
                self._writer(cmd.decode(errors='ignore'))

            # 还原终端设置
            termios.tcsetattr(fd, termios.TCSANOW, old)
            return True
        return False