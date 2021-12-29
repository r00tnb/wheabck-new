from typing import Dict
from api import Session, utils, logger
import threading, socket, select, json, base64, time

class Rule:
    '''描述端口转发规则
    '''

    def __init__(self, session:Session, lhost: str, lport: int, rhost: str, rport: int, upload_buf_size: int, isudp:bool, timeout:float=0) -> None:
        """构造函数

        Args:
            session (Session): session实例
            lhost (str): 本地ip地址
            lport (int): 本地端口
            rhost (str): 远程ip地址
            rport (int): 远程端口
            upload_buf_size (int): 每次上传数据大小限制（单位字节），为0则不会限制大小
            isudp (bool): 是否是UDP转发
            timeout (float, optional): 允许规则空闲的超时时间（单位秒），为0时则不会超时. Defaults to 0.
        """
        self.session = session
        self.lhost = lhost
        self.lport = lport
        self.rhost = rhost
        self.rport = rport
        self.upload_buf_size = upload_buf_size
        self.isudp = isudp
        self.timeout = timeout

        self.recv_host = '' #仅udp
        self.recv_port = 0  #仅udp

        self.__rule_id = utils.random_str()
        self.lock = threading.Lock() # 可用的线程锁

        self.thread = threading.Thread(target=self.run)
        self.thread.setDaemon(True)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM if not isudp else socket.SOCK_DGRAM) # 连接套接字

    @property
    def rule_id(self)->str:
        return self.__rule_id

    @property
    def rule_name(self)->str:
        raise NotImplementedError()

    @property
    def connections_count(self)->int:
        """存活连接的数量

        Returns:
            int: 返回存活连接的数量
        """
        raise NotImplementedError()

    def close(self):
        '''关闭转发规则'''
        raise NotImplementedError()
    
    def run(self):
        '''工作线程函数'''
        raise NotImplementedError()

    def is_alive(self)->bool:
        return self.thread.is_alive()

    def start(self):
        return self.thread.start()

    def flush(self):
        '''刷新当前规则'''
        if self.is_alive():
            self.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM if not self.isudp else socket.SOCK_DGRAM)
        self.thread = threading.Thread(target=self.run)
        self.thread.setDaemon(True)
        return self.start()

class ForwardRule(Rule):
    '''正向转发规则
    '''
    def __init__(self, session: Session, lhost: str, lport: int, rhost: str, rport: int, upload_buf_size: int, isudp: bool, timeout: float) -> None:
        super().__init__(session, lhost, lport, rhost, rport, upload_buf_size, isudp, timeout=timeout)
        self.connections_map:Dict[str, socket.socket] = {} # 当前存在的连接字典,socket都是非阻塞的
        self.max_listen_count = 20 # 最多允许连接的数量

    @property
    def connections_count(self) -> int:
        return len(self.connections_map)

    @property
    def rule_name(self) -> str:
        return f"{self.lhost}:{self.lport} =>{'udp' if self.isudp else 'tcp'}=> {self.rhost}:{self.rport}"

    def _writer(self, conn_id: str):
        """将本地流量写入远程连接端口

        Args:
            conn_id (str): 连接ID
        """
        socket = self.connections_map.get(conn_id)
        if socket is None:
            return
        readl = [socket, ]
        while conn_id in self.connections_map:
            rl, wl, el = select.select(readl, [], [], self.timeout)
            if not rl:
                break
            writebuf = b''
            while True:
                tmp = None
                try:
                    if self.isudp:
                        tmp, addr = socket.recvfrom(1024)
                        self.recv_host, self.recv_port = addr
                    else:
                        tmp = socket.recv(1024)
                except BlockingIOError:
                    pass
                except OSError:
                    self._close(conn_id)
                    return
                if not tmp:
                    break
                writebuf += tmp
            while writebuf: # 限制每次上传的大小
                block = writebuf[:self.upload_buf_size] if self.upload_buf_size > 0 else writebuf
                writebuf = writebuf[self.upload_buf_size:] if self.upload_buf_size > 0 else False
                if self.session.evalfile('forward/writer', dict(conn_id=conn_id, writebuf=block), find_dir=True) is None:
                    logger.warning(f"规则`{self.rule_name}`的连接`{conn_id}`向远程写入数据错误!")
        self._close(conn_id)

    def _reader(self, conn_id: str):
        """从远程连接中读取数据并写入到本地socket

        Args:
            conn_id (str): 连接ID
        """
        sock = self.connections_map.get(conn_id)
        if sock is None:
            return
        while conn_id in self.connections_map:
            ret = self.session.evalfile('forward/reader', dict(conn_id=conn_id), 0, True)
            if ret is None:
                break
            ret = json.loads(ret)
            if ret['code'] == 1:
                data = base64.b64decode(ret['msg'].encode())
                try:
                    if self.isudp:
                        if self.recv_host and self.recv_port:
                            sock.sendto(data, (self.recv_host, self.recv_port))
                        else:
                            logger.warning(f"udp接收未知错误，错误数据：{data}")
                    else:
                        sock.sendall(data)
                except OSError:
                    break
            elif ret['code'] == -1:
                break
        self._close(conn_id)

    def _close(self, conn_id: str):
        """关闭指定连接

        Args:
            conn_id (str): 连接ID
        """
        self.lock.acquire()
        if conn_id in self.connections_map:
            client = self.connections_map.pop(conn_id)
            if client:
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                client.close()
            logger.warning(f"规则`{self.rule_name}`的连接`{conn_id}`已关闭!")
        self.lock.release()

    def _forward(self, conn_id: str):
        """远程连接的数据转发

        Args:
            conn_id (str): 连接ID
        """
        ret = self.session.evalfile('forward/forward', dict(rhost=self.rhost, rport=self.rport, conn_id=conn_id, schema='udp' if self.isudp else 'tcp'),
            0, True)
        if ret is None:
            logger.warning("远程转发请求退出！若流量仍能正确转发可忽略该错误（Windows下的PHP可能出现该问题，可忽略）。")
            return
        ret = json.loads(ret)
        if ret['code'] == -1:  # connect failed
            error = base64.b64decode(ret['msg'].encode()).decode(self.session.options.get_option('encoding').value, 'ignore')
            logger.error("连接失败： "+error)
        elif ret['code'] == 1:
            logger.info(f"规则`{self.rule_name}`的连接`{conn_id}`远程转发请求已正确关闭!", False)

        self._close(conn_id)

    def close(self):  # 关闭所有连接并退出线程
        ids = list(self.connections_map.keys())
        for i in ids:
            self._close(i)
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        self.thread.join(5)
        if self.is_alive():
            utils.kill_thread(self.thread.ident)


    def run(self):
        try:
            self.sock.bind((self.lhost, self.lport))
            if not self.isudp:
                self.sock.listen(self.max_listen_count)
        except OSError as e:
            logger.error(f"地址绑定错误： {e}")
            return
        thread_list = []
        while True:
            if not self.isudp:
                try:
                    sock, addr = self.sock.accept()
                except OSError:
                    break
                logger.info(f"`{addr}`连接过来了！")
            else:
                sock = self.sock

            sock.setblocking(False)
            conn_id = utils.random_str()
            self.connections_map[conn_id] = sock

            forwardwork = threading.Thread(target=self._forward, args=(
                conn_id, ), name=f"{conn_id}-forward on rule `{self.rule_name}`")
            readerthread = threading.Thread(target=self._reader, args=(
                conn_id, ), name=f"{conn_id}-reader on rule `{self.rule_name}`")
            writerthread = threading.Thread(target=self._writer, args=(
                conn_id, ), name=f"{conn_id}-writer on rule `{self.rule_name}`")
            thread_list.append(forwardwork)
            thread_list.append(readerthread)
            thread_list.append(writerthread)

            forwardwork.setDaemon(True)
            readerthread.setDaemon(True)
            writerthread.setDaemon(True)
            forwardwork.start()
            time.sleep(1)
            readerthread.start()
            writerthread.start()

            if self.isudp:
                break

        for t in thread_list:
            t.join()


class ReverseRule(Rule):
    '''反向转发规则
    '''

    def __init__(self, session: Session, lhost: str, lport: int, rhost: str, rport: int, upload_buf_size: int, isudp: bool, timeout: float = 0) -> None:
        super().__init__(session, lhost, lport, rhost, rport, upload_buf_size, isudp, timeout=timeout)
        self.conn_id:str = '' # 标示连接，或其他用途
        self._conn_count = 0

        self.recv_host = self.lhost
        self.recv_port = self.lport

        self.writer_thread_id = None

    @property
    def rule_name(self) -> str:
        return f"{self.lhost}:{self.lport} <={'udp' if self.isudp else 'tcp'}<= {self.rhost}:{self.rport}"

    @property
    def connections_count(self) -> int:
        return self._conn_count

    def is_closed(self):
        '''远程是否已关闭'''
        self.lock.acquire()
        c = self._conn_count
        self.lock.release()
        return not c

    def _writer(self):
        sock = self.sock
        readl = [sock, ]
        while not self.is_closed():
            rl, wl, el = select.select(readl, [], [], 180)
            if not rl:
                break
            writebuf = b''
            while True:
                tmp = None
                try:
                    if self.isudp:
                        tmp, addr = sock.recvfrom(1024)
                    else:
                        tmp = sock.recv(1024)
                except BlockingIOError:
                    pass
                except OSError:
                    self._close()
                    return
                if not tmp:
                    break
                writebuf += tmp
            while writebuf:
                block = writebuf[:self.upload_buf_size] if self.upload_buf_size > 0 else writebuf
                writebuf = writebuf[self.upload_buf_size:] if self.upload_buf_size > 0 else False
                self.session.evalfile('reverse/writer', dict(sessionid=self.conn_id, writebuf=block), find_dir=True)

        self._close()

    def _reader(self):
        sock = self.sock
        while not self.is_closed():
            ret = self.session.evalfile('reverse/reader', dict(sessionid=self.conn_id), 0, True)
            if ret is None:
                break
            ret = json.loads(ret)
            if ret['code'] == 1:
                data = base64.b64decode(ret['msg'].encode())
                try:
                    if self.isudp:
                        if self.recv_host and self.recv_port:
                            sock.sendto(data, (self.recv_host, self.recv_port))
                        else:
                            logger.warning(f"udp接收未知错误，错误数据：{data}")
                    else:
                        sock.sendall(data)
                except OSError:
                    break
            elif ret['code'] == -1:
                break

        self._close()

    def _forward(self):
        '''执行前需要把webshell超时时间设置为无限
        '''
        ret = self.session.evalfile('reverse/forward', dict(rhost=self.rhost, rport=self.rport, sessionid=self.conn_id, schema='udp' if self.isudp else 'tcp')
            , 0, True)
        if ret is None:
            logger.warning("远程转发请求退出！若流量仍能正确转发可忽略该错误（Windows下的PHP可能出现该问题，可忽略）。")
            return
        ret = json.loads(ret)
        if ret['code'] == -1:
            error = base64.b64decode(ret['msg'].encode()).decode(self.session.options.get_option('encoding').value, 'ignore')
            logger.error(error)
        elif ret['code'] == 0:
            logger.error(f"规则`{self.rule_name}`的连接远程转发无法使用socket!")
        elif ret['code'] == 1:
            logger.info(f"规则`{self.rule_name}`的连接远程转发已正确关闭!", False)
        else:
            logger.error(f"规则`{self.rule_name}`转发请求发生未知错误!")
            logger.error(f"错误数据： {ret}")

        self._close()
        utils.kill_thread(self.writer_thread_id)

    def _close(self):
        self.lock.acquire()
        c = self._conn_count
        self._conn_count -= 1
        if self._conn_count < 0:
            self._conn_count = 0
        self.lock.release()
        if c<1:
            return
        self.session.evalfile('reverse/close', dict(sessionid=self.conn_id), find_dir=True)
        logger.info(f"规则`{self.rule_name}`的连接已关闭!", False)

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        self.thread.join(5)
        if self.is_alive():
            utils.kill_thread(self.thread.ident)

        self._close()
        

    def _test_connect(self) -> bool:
        """测试远程是否已连接，若连接了则函数会返回，否则一直阻塞

        Returns:
            bool: 连接成功返回True，其他原因失败返回False
        """
        ret = self.session.evalfile('reverse/test_connect', dict(sessionid=self.conn_id), 0, True)
        if ret is None:
            logger.error("未知原因导致连接关闭!(windows下的PHP可能会造成此情况，请在超时时间内建立反向转发)")
            return False
        if ret == b'1':
            logger.info(f"规则`{self.rule_name}`产生了一个反向连接!", True)
            return True
        elif ret == b"-1":
            self._close()
        else:
            logger.error(f"规则`{self.rule_name}`测试连接请求产生了一个未知错误!")
            logger.error(f"错误数据： {ret}")
            self._close()
        return False

    def run(self):
        thread_list = []
        self.conn_id = utils.random_str()

        forwardwork = threading.Thread(target=self._forward)
        forwardwork.setDaemon(True)
        thread_list.append(forwardwork)
        forwardwork.start()
        time.sleep(1)
        while self._test_connect():
            self._conn_count += 1
            if not self.isudp:
                self.sock.settimeout(5)
                try:
                    self.sock.connect((self.lhost, self.lport))
                except OSError as e:
                    logger.error(f"规则`{self.rule_name}`连接到本地地址`{self.lhost}:{self.lport}`失败！")
                    logger.error(e.strerror)
                    self._close()
                    break
            

            self.sock.setblocking(False)
            readerthread = threading.Thread(target=self._reader, name=f"{self.rule_name}-reader")
            writerthread = threading.Thread(target=self._writer, name=f"{self.rule_name}-writer")
            readerthread.setDaemon(True)
            writerthread.setDaemon(True)
            thread_list.append(readerthread)
            thread_list.append(writerthread)
            readerthread.start()
            writerthread.start()
            self.writer_thread_id = writerthread.ident
            break

        for t in thread_list:
            t.join()

        self._conn_count = 0
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        self.sock.close()