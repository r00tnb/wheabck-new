from api import utils, logger, Session
import socket
import struct
import json
import base64
import threading
import select

class Connection:
    '''存储连接信息，以及该连接相关操作
    '''

    ACTION_CONNECT = 1
    ACTION_READ = 2
    ACTION_WRITE = 3
    ACTION_CLOSE = 4

    REP_SUCCESS = 0
    REP_FAILED = 1

    def __init__(self, client:socket.socket, rhost: str, rport: int, lhost: str, lport: int, iptype: int, server):
        self.client = client # 已经和本地程序建立连接的socket,已设置为非阻塞模式
        self.rhost = rhost # 远程地址
        self.rport = rport # 远程端口
        self.lhost = lhost # 本地客户端地址与client对应
        self.lport = lport # 本地客户端端口与client对应
        self.iptype = iptype # 为4表示ipv4地址，为6表示ipv6地址
        self.server = server # SocksProxy对象
        self.session = self.server.session
        self.id = 0 # 当转发成功时会从服务端获取，当关闭该连接时置为0，可以通过该值判断连接是否存活

    def is_alive(self)-> bool:
        if self.id:
            return True
        return False

    def __str__(self)-> str:
        return f"({self.lhost}, {self.lport}) => ({self.rhost}, {self.rport})"

    def exec_action(self, action: int, data: bytes=b'')-> int:
        '''向远程UDP服务器执行动作
        '''
        ret = None
        encoding = self.session.options.get_option('encoding').value
        timeout = self.session.options.get_option('timeout').value
        if action == self.ACTION_CONNECT:
            timeout = 20
        elif action == self.ACTION_READ:
            timeout = 0

        ret = self.session.evalfile('action', dict(action=action, shost=self.server.shost, sport=self.server.sport, sockid=self.id, 
            rhost=self.rhost, rport=self.rport, type=self.iptype, data=data), timeout, True)

        if ret is None:
            return self.REP_FAILED

        ret = json.loads(ret)
        if ret['code'] == 1:
            if action == self.ACTION_CONNECT:
                self.id = ret['msg']
                logger.info(f"连接`{self}`创建成功!", True)
            elif action == self.ACTION_CLOSE:
                self.id = 0
                logger.info(f"连接`{self}`关闭!", False)
            elif action == self.ACTION_READ:
                msg = base64.b64decode(ret['msg'].encode())
                self.client.sendall(msg, 0)
            return self.REP_SUCCESS
        elif ret['code'] == -1:
            msg = base64.b64decode(ret['msg'].encode()).decode(encoding, 'ignore')
            logger.error("远程socket发生错误: "+msg)
        elif ret['code'] == -2:
            code = ret['msg']
            logger.error(f"远程错误代码 `{code}`!")
            if action == self.ACTION_READ:
                logger.info("远程数据读取错误!")
        if action == self.ACTION_CONNECT:
            logger.error(f"连接`{self}`创建失败!")
        return self.REP_FAILED


class SocksProxy(threading.Thread):
    '''socks服务端，实现基本功能
    '''

    SOCKS_VERSION_4 = 4
    SOCKS_VERSION_5 = 5
    ATYP_IPV4 = 1
    ATYP_FQDN = 3
    ATYP_IPV6 = 4
    CMD_CONNECT = 1
    CMD_BIND = 2
    CMD_UDP_ASSOCIATE = 3

    def __init__(self, session:Session):
        super().__init__()
        self.session = session
        self.port = 1080
        self.host = '0.0.0.0'
        self.shost = '127.0.0.1' # 远程服务器监听地址
        self.sport = 50000 # 远程服务器监听UDP端口
        self.ldns = False # 是否本地解析域名

        self.connections = []
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.max_listen_count = 50 # 最大监听数量
        self.upload_buf_size = 4096 # 限制每次上传到远程的数据包大小,为0 时不限制

        self.running = False
        self._lock = threading.Lock()
        self.name = "SocksProxy Local Server"

    def shakehands(self, client:socket.socket, addr:tuple)->Connection:
        '''完成socks握手过程
        '''
        # 客户端握手
        ver, l = struct.unpack('!BB', client.recv(2))
        assert ver in (self.SOCKS_VERSION_4, self.SOCKS_VERSION_5), f"不支持的协议类型`{ver}`"
        assert l > 0, "错误的方法"
        methods = struct.unpack("!"+"B"*l, client.recv(l)) # 备用

        # 无验证方式
        client.sendall(struct.pack('!BB', ver, 0))

        # 处理客户端转发请求
        ver, cmd, rsv, atyp = struct.unpack('!BBBB', client.recv(4))
        assert ver in (self.SOCKS_VERSION_4, self.SOCKS_VERSION_5), f"不支持的协议类型`{ver}`"
        assert rsv == 0, f"Reserved field must be 0, actually `{rsv}`"
        dst_addr = ''
        dst_port = 0
        if atyp == self.ATYP_IPV4:
            dst_addr = socket.inet_ntoa(client.recv(4))
        elif atyp == self.ATYP_IPV6:
            dst_addr = socket.inet_ntop(socket.AF_INET6, client.recv(16))
        elif atyp == self.ATYP_FQDN:
            l = struct.unpack("!B", client.recv(1))[0]
            assert l > 0, f"ATYP is FQDN, but domain length `{l}` is invalid"
            dst_addr = self._handle_domain(client.recv(l).decode())
        else:
            raise AssertionError(f"Unknown atyp `{atyp}`")
        dst_port = struct.unpack('!H', client.recv(2))[0]

        conn = Connection(client, dst_addr, dst_port, addr[0], addr[1], 
            6 if atyp == self.ATYP_IPV6 else 4, self)
        if cmd == self.CMD_CONNECT:
            code = conn.exec_action(Connection.ACTION_CONNECT)
            if code == 0:# 转发成功
                client.sendall(struct.pack("!BBBB", ver, 0, rsv, self.ATYP_IPV4)+
                    socket.inet_pton(socket.AF_INET, self.host)+struct.pack("!H", self.port))
                client.setblocking(False) # 设置非阻塞模式
                return conn
            else:
                client.sendall(struct.pack("!BBBB", ver, code, rsv, self.ATYP_IPV4)+
                    socket.inet_pton(socket.AF_INET, self.host)+struct.pack("!H", self.port))
                raise AssertionError("连接转发失败!")
        elif cmd == self.CMD_BIND:
            pass
        elif cmd == self.CMD_UDP_ASSOCIATE:
            pass
        else:
            raise AssertionError(f"未知的命令字段`{cmd}`")

        return None

    def _handle_domain(self, domain: str)-> str:
        '''处理域名，可能本地解析，也可远程解析
        '''
        if self.ldns:
            return socket.gethostbyname(domain)
        return domain

    def start_remote_udp_server(self):
        '''开启远程UDP服务器，用于转发请求
        '''
        while True:
            ret = self.session.evalfile('proxy', dict(host=self.shost, port=self.sport), 0, True)
            if ret is None:
                break
            
            ret = json.loads(ret)
            if ret['code'] == 1:
                break
            elif ret['code'] in (-1, -2):
                msg = base64.b64decode(ret['msg'].encode()).decode(self.session.options.get_option('encoding').value, 'ignore')
                logger.error("远程转发服务错误: "+msg)
                if ret['code'] == -2:
                    logger.error(f"远程转发服务端口（UDP）`{self.sport}`绑定失败!")
            elif ret['code'] == -3:
                logger.error("远程转发服务错误: 未知的错误原因导致`select`函数执行退出")
            break
        
        with self._lock:
            self.running = False
            try:
                self.server.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.server.close()

    def close(self):
        with self._lock:
            if self.running:
                encoding = self.session.options.get_option('encoding').value
                ret = self.session.evalfile('action', dict(action=Connection.ACTION_CLOSE, shost=self.shost, sport=self.sport, sockid=0), find_dir=True)
                if ret is None:
                    logger.error("远程转发服务关闭失败!")
                    return
                ret = json.loads(ret)
                if ret['code'] == 1:
                    for conn in self.connections:
                        conn.client.close()
                    self.running = False
                    try:
                        self.server.shutdown(socket.SHUT_RDWR)
                    except:
                        pass
                    self.server.close()
                    logger.info("socks正向转发服务已关闭!")
                    return
                elif ret['code'] == -1:
                    msg = base64.b64decode(ret['msg'].encode()).decode(encoding, 'ignore')
                    logger.error(msg)
                elif ret['code'] == -2:
                    code = ret['msg']
                    logger.error(f"远程错误代码 `{code}`!")

                logger.error("远程转发服务关闭失败!")
                
    def reader(self, conn: Connection):
        '''从远端读
        '''
        while conn.is_alive() and self.running:
            conn.exec_action(Connection.ACTION_READ)

    def writer(self, conn: Connection):
        '''向远端写
        '''
        read = [conn.client, ]
        while conn.is_alive() and self.running:
            r, w, e = select.select(read, [], [])
            if not r:
                logger.error(f"Reader thread exit on `{conn}`")
                conn.exec_action(Connection.ACTION_CLOSE)
                break
            writebuf = b''
            while True:
                tmp = None
                try:
                    tmp = conn.client.recv(4096)
                except BlockingIOError:
                    pass
                except OSError:
                    conn.exec_action(Connection.ACTION_CLOSE)
                    break
                if not tmp:
                    break
                writebuf += tmp
            while writebuf: # 限制每次上传的大小
                block = writebuf[:self.upload_buf_size] if self.upload_buf_size > 0 else writebuf
                writebuf = writebuf[self.upload_buf_size:] if self.upload_buf_size > 0 else False
                conn.exec_action(Connection.ACTION_WRITE, block)

    def run(self):
        '''开启服务
        '''
        self.running = True
        try:
            self.server.bind((self.host, self.port))
        except:
            logger.error(f"本地转发服务绑定`{self.host}, {self.port}`失败!")
            return
        self.server.listen(self.max_listen_count)
        
        thread_list = []
        udp_server_thread = threading.Thread(target=self.start_remote_udp_server, name="SocksProxy Remote UDP Server")
        thread_list.append(udp_server_thread)
        udp_server_thread.setDaemon(True)
        udp_server_thread.start()

        while self.running:
            try:
                client, addr = self.server.accept()
                logger.info(f"来自`{addr}`的连接", True)
            except OSError as e:
                break
            try:
                conn = self.shakehands(client, addr)
            except (AssertionError, OSError) as e:
                logger.error(e)
                client.close()
            else:
                logger.info(f"来自`{addr}`的连接握手成功!", True)
                read_thread = threading.Thread(target=self.reader, args=(conn, ), name=f"SocksProxy read thread on `{conn}`")
                write_thread = threading.Thread(target=self.writer, args=(conn, ), name=f"SocksProxy write thread on `{conn}`")
                thread_list.append(read_thread)
                thread_list.append(write_thread)
                read_thread.setDaemon(True)
                write_thread.setDaemon(True)
                read_thread.start()
                write_thread.start()

        for t in thread_list:
            t.join(5)
            if t.is_alive():
                utils.kill_thread(t.ident)
        logger.info("清理完毕!")
