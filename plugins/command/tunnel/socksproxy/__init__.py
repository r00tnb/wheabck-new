from typing import List
from api import Session, logger, tablor, colour, Plugin, Command, CommandReturnCode, CommandType, Cmdline
import argparse
import re
from .proxy import SocksProxy

def get_plugin_class():
    return SocksProxyPlugin

class SocksProxyPlugin(Plugin, Command):
    name = 'socks正向代理'
    description = "通过HTTP隧道进行socks正向代理"
    command_name = 'socksproxy'
    command_type = CommandType.POST_COMMAND

    def __init__(self):
        super().__init__()
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        subparse = self.parse.add_subparsers()
        start_parse = subparse.add_parser('start', help="开启socks正向代理服务")
        start_parse.set_defaults(func=self._start)

        stop_parse = subparse.add_parser('stop', help="停止当前服务")
        stop_parse.set_defaults(func=self._stop)

        restart_parse = subparse.add_parser('restart', help="重启服务")
        restart_parse.set_defaults(func=self._restart)

        status_parse = subparse.add_parser('status', help="查看服务状态信息")
        status_parse.set_defaults(func=self._status)

        config_parse = subparse.add_parser('config', help="设置服务参数")
        config_parse.set_defaults(func=self._config)
        config_parse.add_argument('-l', '--lhost', help="本地监听地址")
        config_parse.add_argument('-p', '--lport', help="本地监听端口", type=int)
        config_parse.add_argument('-r', '--rhost', help="远程代理监听地址")
        config_parse.add_argument('-P', '--rport', help="远程代理监听端口（UDP端口）", type=int)
        config_parse.add_argument('-d', '--dns', help="是否本地解析dns（默认远程解析）", action='store_true')
        config_parse.add_argument('-s', '--uploadsize', help="每次上传的数据包大小。能够使用单位b（字节）、k（千字节）、m（兆字节）默认b.例如1024, 1024b, 1024k等。若设置为0（默认），则数据将在一次请求中上传", 
            type=self._getsize)
        self.help_info = self.parse.format_help()

        self.proxy:SocksProxy = None
        self.my_config = {
            'lhost':'127.0.0.1',
            'lport':1080,
            'rhost':'127.0.0.1',
            'rport':50000,
            'dns': False,
            'uploadsize':0
        }

    def _getsize(self, size: str)-> int:
        '''用于转换传入的--uploadsize参数
        '''
        size = size.strip().rstrip('bB').lower()
        try:
            util = size[-1]
            if util not in 'km':
                return int(size)

            size = float(size[:-1])
            if util == 'k':
                size *= 1024
            elif util == 'm':
                size *= 1024*1024
            return int(size)
        except Exception as e:
            logger.error(f"上传数据包大小参数`{size}`格式错误!")
            raise e

    def on_loading(self, session: Session) -> bool:
        session.register_complete_func(self.docomplete)
        return super().on_loading(session)

    def _start(self, args:argparse.Namespace)->CommandReturnCode:
        if self.is_running():
            logger.error("socks代理服务已经是开启的！")
            return CommandReturnCode.CANCEL
        self.proxy = SocksProxy(self.session)
        self.proxy.host = self.my_config['lhost']
        self.proxy.port = self.my_config['lport']
        self.proxy.shost = self.my_config['rhost']
        self.proxy.sport = self.my_config['rport']
        self.proxy.ldns = self.my_config.get('dns', False)
        self.proxy.upload_buf_size = self.my_config['uploadsize']
        self.proxy.setDaemon(True)
        self.proxy.start()
        logger.info(f"socks正向代理在`{self.proxy.host}, {self.proxy.port}`开始监听...", True)
        return CommandReturnCode.SUCCESS

    def _stop(self, args:argparse.Namespace)->CommandReturnCode:
        if self.is_running():
            logger.info(f"socks正向代理`{self.proxy.host}, {self.proxy.port}`正在停止...")
            self.proxy.close()
            logger.info(f"socks正向代理本地服务`{self.proxy.host}, {self.proxy.port}`已停止!", False)
            return CommandReturnCode.SUCCESS
        logger.error("socks代理服务未在运行中！")
        return CommandReturnCode.CANCEL

    def _restart(self, args:argparse.Namespace)->CommandReturnCode:
        if self.is_running():
            self.proxy.close()
        proxy = SocksProxy(self)
        if self.proxy is not None:
            proxy.host = self.proxy.host
            proxy.port = self.proxy.port
            proxy.shost = self.proxy.shost
            proxy.sport = self.proxy.sport
            proxy.ldns = self.proxy.ldns
            proxy.upload_buf_size = self.proxy.upload_buf_size
        else:
            proxy.host = self.my_config['lhost']
            proxy.port = self.my_config['lport']
            proxy.shost = self.my_config['rhost']
            proxy.sport = self.my_config['rport']
            proxy.ldns = self.my_config.get('dns', False)
            proxy.upload_buf_size = self.my_config['uploadsize']
        proxy.setDaemon(True)
        proxy.start()
        self.proxy = proxy
        logger.info(f"socks正向代理在`{self.proxy.host}, {self.proxy.port}`重新开始监听...", True)
        return CommandReturnCode.SUCCESS

    def _status(self, args:argparse.Namespace)->CommandReturnCode:
        table = []
        if self.proxy is not None:
            table.append(['状态', colour.colorize('运行中', 'bold', 'green') if self.proxy.is_alive() else colour.colorize('停止', 'bold', 'red')])
            table.append(['本地监听地址', self.proxy.host])
            table.append(['本地监听端口', self.proxy.port])
            table.append(['远程监听地址', self.proxy.shost])
            table.append(['远程监听端口', self.proxy.sport])
            table.append(['本地解析域名', '是' if self.proxy.ldns else '否'])
            table.append(['上传分片大小', self.proxy.upload_buf_size if self.proxy.upload_buf_size else "不分片"])
        else:
            table.append(['状态', colour.colorize('停止', 'bold', 'red')])
            table.append(['本地监听地址', self.my_config['lhost']])
            table.append(['本地监听端口', self.my_config['lport']])
            table.append(['远程监听地址', self.my_config['rhost']])
            table.append(['远程监听端口', self.my_config['rport']])
            table.append(['本地解析域名', '是' if self.my_config.get('dns', False) else '否'])
            table.append(['上传分片大小', self.my_config['uploadsize'] if self.my_config['uploadsize'] else "不分片"])

        print(tablor(table, False, True))
        return CommandReturnCode.SUCCESS

    def _config(self, args:argparse.Namespace)->CommandReturnCode:
        if self.is_running():
            logger.error("socks正向代理正在运行，无法设置！")
            return CommandReturnCode.FAIL
        if args.lhost is not None:
            self.my_config['lhost'] = args.lhost
            logger.info(f"lhost => {args.lhost}", True)
        if args.lport is not None:
            self.my_config['lport'] = args.lport
            logger.info(f"lport => {args.lport}", True)
        if args.rhost is not None:
            self.my_config['rhost'] = args.rhost
            logger.info(f"rhost => {args.rhost}", True)
        if args.rport is not None:
            self.my_config['rport'] = args.rport
            logger.info(f"rport => {args.rport}", True)
        if args.dns is not None:
            self.my_config['dns'] = args.dns
            logger.info(f"dns => {args.dns}", True)
        if args.uploadsize is not None:
            self.my_config['uploadsize'] = args.uploadsize
            logger.info(f"uploadsize => {args.uploadsize}", True)

        return CommandReturnCode.SUCCESS

    def run(self, args: Cmdline)-> int:
        args = self.parse.parse_args(args.options)
        if hasattr(args, 'func'):
            return args.func(args)
        self.parse.error("未提供子命令！")
        return CommandReturnCode.FAIL

    def is_running(self)->bool:
        '''服务是否在运行
        '''
        return self.proxy is not None and self.proxy.is_alive()

    def docomplete(self, text: str)-> List[str]:
        result = []
        match = re.fullmatch(r'(%s +)(\w*)'%self.command_name, text)
        if match:
            for key in ['start', 'stop', 'restart', 'status', 'config']:
                if key.startswith(match.group(2).lower()):
                    result.append(match.group(1)+key+' ')
        return result

    def on_loaded(self):
        my_config = self.session.load_json(self.command_name)
        if my_config:
            self.my_config = my_config

    def on_destroy(self):
        self.session.save_json(self.command_name, self.my_config)
        if self.is_running():
            self._stop(None)