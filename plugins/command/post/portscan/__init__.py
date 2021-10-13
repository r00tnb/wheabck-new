from math import log
from typing import Any, Dict, List, Tuple
from api import Session, logger, colour, tablor, Plugin, Command, CommandReturnCode, CommandType, Cmdline, OSType
import argparse
import re
import socket
import struct
import csv
import json
import base64
from .worker import Worker
import enum, time, os

def get_plugin_class():
    return PortScanPlugin

class  TransType(enum.Enum):
    TCP = 1
    UDP = 2
    ALL = 3
    UNKNOWN = 4

    @classmethod
    def from_name(cls, name:str):
        """从名称获取传输协议类型

        Args:
            name (str): 类型名称

        Returns:
            TransType: 传输类型实例
        """
        name = name.upper()
        try:
            return TransType[name]
        except:
            return TransType.UNKNOWN

class Port:

    def __init__(self, port: int, trans_type: TransType, name:str, note: str=''):
        self.port = port # 端口号
        self.trans_type = trans_type # 传输协议类型
        self.name = name # 端口对应服务名称
        self.note = note # 端口注释

    def __eq__(self, o: object) -> bool:
        return o.port == self.port and o.trans_type == self.trans_type

class ServicePortMap:
    '''描述常见端口和其服务的映射
    '''

    def __init__(self, csv_path:str=None) -> None:
        """从csv文件中读取端口和服务的映射信息，CSV文件可以是https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml中获取的
        其前四列分别是：服务名、端口号、传输协议、简短描述

        Args:
            csv_path (str): CSV文件路径
        """
        self.__service_list:List[Port] = [] # 存储端口信息
        if csv_path is not None:
            self.add_from_file(csv_path)

    def add_from_file(self, csv_file:str):
        with open(csv_file, 'r', newline='', encoding='utf8') as f:
            reader = csv.reader(f)
            for p in reader:
                if reader.line_num == 1:# 第一行略过
                    continue
                try:
                    service = p[0].strip()
                    port = int(p[1].strip())
                    t = p[2].strip()
                    note = p[3].strip()
                    pp = Port(port, TransType.from_name(t), service, note)
                    if pp in self.__service_list:# 去重
                        continue
                    self.append_port(pp)
                except:
                    logger.debug(f"加载第`{reader.line_num}`行失败!")
    def add_from_list(self, ports:List[Port]):
        self.__service_list.extend(ports)

    @property
    def count(self)->int:
        return len(self.__service_list)
    
    @property
    def port_list(self)->List[Port]:
        return self.__service_list.copy()

    def append(self, port: int, trans_type: TransType, name:str, note: str='')->bool:
        if port:
            self.__service_list.append(Port(port, trans_type, name, note))
            return True
        return False

    def append_port(self, port:Port)->bool:
        if port:
            self.__service_list.append(port)
            return True
        return False
    
    def get(self, port:int, trans_type:TransType)->Port:
        for p in self.__service_list:
            if p.port == port and trans_type == p.trans_type:
                return p
        return None


class PortScanPlugin(Plugin, Command):
    name = "端口扫描"
    description = "通过webshell进行端口扫描"
    command_name = 'portscan'
    command_type = CommandType.POST_COMMAND

    default_ports:ServicePortMap = None # 默认要扫描的端口列表
    
    def __init__(self):
        super().__init__()
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        sub_parses = self.parse.add_subparsers()
        report_parse = sub_parses.add_parser("report", help="查看扫描报告")
        report_parse.set_defaults(func=self._report)
        report_parse.add_argument('-l', '--list', help="列出所有报告", action='store_true')
        report_parse.add_argument('-v', '--view', help="查看指定报告ID的报告内容", type=int)
        report_parse.add_argument('-d', '--delete', help="删除指定ID的报告，指定-1则删除全部", type=int)

        scan_parse = sub_parses.add_parser('scan', help="进行端口扫描")
        scan_parse.set_defaults(func=self._scan)
        scan_parse.add_argument('-n', '--nodetect', help="不进行主机存活检查.", action="store_true")
        scan_parse.add_argument('-U', '--host-detect-udp', help="使用UDP检查主机是否存活（不准确），当没有足够权限时可尝试该方法", action="store_true")
        scan_parse.add_argument('-T', '--type', help="指定要检查的端口传输协议类型，默认检查所有类型", choices=[t.name for t in TransType if t!=TransType.UNKNOWN], default='ALL')
        scan_parse.add_argument('-p', '--ports', help="指定要扫描的端口（不指定该参数则扫描默认端口），如：1-65535， 1433 22等.", nargs='+')
        scan_parse.add_argument('-t', '--threads', help="指定扫描的线程数量（默认一个线程）.", default=1, type=int)
        scan_parse.add_argument('--timeout', help="指定等待端口响应的超时时间，单位毫秒（默认1000 ms）.", default=1000, type=int)
        scan_parse.add_argument('hosts', help="指定要扫描的主机，如192.168.1.1/24, 192.168.1.10-192.168.1.100, 192.168.1.2,...", nargs='+')
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        session.register_complete_func(self.docomplete)
        return super().on_loading(session)

    def save_report(self, ip:str, open_ports:List[Port]):
        """保存一条扫描结果

        Args:
            ip (str): 目标ip地址
            open_ports (List[Port]): 开发的端口列表
        """
        reports = self.session.load_json(self.command_name)
        if not reports:
            reports = {}
        tmp = []
        for p in open_ports:
            tmp.append({'port':p.port, 'name':p.name, 'note':p.note, 'trans_type':p.trans_type.name})
        reports[ip] = tmp
        self.session.save_json(self.command_name, reports)

    def get_reports(self)->Dict[str, ServicePortMap]:
        """获取扫描结果

        Returns:
            Dict[str, ServicePortMap]: 返回结果字典
        """
        reports = self.session.load_json(self.command_name)
        if not reports:
            return {}
        for ip, lp in reports.items():
            tmp = ServicePortMap()
            for p in lp:
                tmp.append(p['port'], TransType.from_name(p['trans_type']), p['name'], p['note'])
            reports[ip] = tmp
        return reports


    def _report(self, args:argparse.Namespace)->CommandReturnCode:
        reports = self.get_reports()
        if args.delete:
            ID = args.delete
            i = 1
            for ip in list(reports.keys()):
                if ID == -1 or ID == i:
                    reports.pop(ip)
                    logger.info(f"已删除`{ip}`的扫描结果！")
                i += 1
            return CommandReturnCode.SUCCESS
        elif args.view:
            ID = args.view
            i = 1
            for ip in reports:
                if ID == i:
                    table = [['端口号', '传输协议', '服务名', '描述']]
                    for p in reports[ip].port_list:
                        table.append([p.port, p.trans_type.name, p.name, p.note])
                    print(tablor(table, border=False, title=ip))
                    return CommandReturnCode.SUCCESS
                i += 1
            logger.error(f"不存在的ID`{ID}`！")
        else:
            table = [['ID', '存活IP', '存活端口数量']]
            i = 1
            for ip, m in reports.items():
                table.append([i, ip, m.count])
                i += 1
            print(tablor(table, border=False))
            return CommandReturnCode.SUCCESS
        return CommandReturnCode.FAIL

    def _scan(self, args:argparse.Namespace)->CommandReturnCode:
        trans_type = TransType.from_name(args.type)
        hosts = self._parse_hosts(args.hosts)
        ports_map = self._parse_ports(args.ports, trans_type)

        if not hosts:
            logger.error("无可用IP!")
            return CommandReturnCode.FAIL

        logger.info(f"使用`{args.threads}`个线程进行扫描")
        if args.nodetect:
            logger.info("不进行主机存活扫描!")
        
        if not args.nodetect:# 主机存活检测
            logger.info(f"进行主机存活扫描, 使用`{'UDP' if args.host_detect_udp else 'PING'}`方法.")
            logger.info(f"扫描主机范围`{args.hosts}`")
            hosts = self.host_survival_scan(hosts, args.timeout, args.threads, args.host_detect_udp)

        logger.info(f"进行`{args.ports if args.ports else '默认'}`端口扫描, 扫描类型为`{trans_type.name}`")
        for ip in hosts:
            m = self.port_scan(ip, args.timeout, ports_map, args.threads)
            self.save_report(ip, m.port_list)
        logger.info("所有端口扫描完毕！")
        return CommandReturnCode.SUCCESS

    def run(self, args: Cmdline)-> CommandReturnCode:
        args = self.parse.parse_args(args.options)
        if hasattr(args, 'func'):
            return args.func(args)
        self.parse.error("未提供子命令！")
        return CommandReturnCode.FAIL
        
    def _parse_ports(self, ports:list, trans_type:TransType)->ServicePortMap:
        '''解析端口范围，返回端口列表
        '''
        if self.default_ports is None:
            self.default_ports = ServicePortMap(os.path.join(os.path.dirname(__file__), 'service-names-port-numbers.csv'))
        ret = ServicePortMap()
        trans_type_list = []
        if TransType.ALL == trans_type:
            trans_type_list = [TransType.TCP, TransType.UDP]
        else:
            trans_type_list = [trans_type]
        if not ports:
            return self.default_ports
        for p in ports:
            min_port = 0
            max_port = 0
            try:
                if '-' in p:
                    p1, p2 = p.split('-')
                    min_port = int(p1)
                    max_port = int(p2)
                else:
                    min_port = max_port = int(p)
                for port in range(min_port, max_port+1):
                    for t in trans_type_list:
                        pp = self.default_ports.get(port, t)
                        if pp:
                            ret.append_port(pp)
                        else:
                            ret.append(port, t, 'unknow')
            except Exception as e:
                print(e)
                logger.error(f"端口`{p}`解析失败!")
        return ret


    def _parse_hosts(self, hosts:List[str])->List[str]:
        '''解析ip范围，返回ip字符串的列表
        '''
        ret = []
        if not hosts: # 若未指定hosts，则使用上传扫描结果中存活的主机
            logger.warning("No host specified, use the host that alive the last scan.")
            for ip in self._scan_result:
                ret.append(ip)
                logger.info(f"Using alive host {ip}")
            return ret
        for h in hosts:
            h = h.strip()
            min_ip = 0
            max_ip = 0
            try:
                if '/' in h:
                    ip, mask = h.split('/')
                    ip = struct.unpack("!L", socket.inet_aton(ip))[0]
                    mask = int(mask)
                    if mask <= 0 or mask >= 32:
                        raise ValueError('mask is error!')
                    min_ip = ip & (2**32-2**(32-mask))+1
                    max_ip = min_ip+2**(32-mask)-3
                elif '-' in h:
                    ip0, ip1 = h.split('-')
                    min_ip = struct.unpack("!L", socket.inet_aton(ip0))[0]
                    max_ip = struct.unpack("!L", socket.inet_aton(ip1))[0]
                    if min_ip > max_ip:
                        raise ValueError('IP range is error!')
                else:
                    min_ip = max_ip = struct.unpack("!L", socket.inet_aton(h))[0]
                for ip in range(min_ip, max_ip+1):
                    ret.append(socket.inet_ntoa(struct.pack('!L', ip)))
            except:
                logger.error(f"Host `{h}` format error!")
            
        return ret

    def _update_port_note_by_response(self, port:Port):
        '''根据响应修改端口的说明
        '''
        if port.note:# 有默认说明的暂时不识别
            return
        if not hasattr(port, 'response'):
            return
        text = port.response.decode(self.session.options.get_option('encoding').value, 'ignore')
        if re.match(r'(?i)HTTP/\d+\.\d+ \d+ .*\r\n', text):
            port.note = "http"
        elif re.match(r'(?i)SSH-', text):
            port.note = "ssh"
        else:
            port.note = f"Unknown service[{text[:50].strip()}]"

    def _port_scan_handler(self, ports_list:List[Port], ip:str, connect_timeout:int)-> tuple:
        '''端口扫描处理函数
        '''
        result = []
        ret = self.session.evalfile("port_scan", dict(ip=ip, ports=','.join([str(i.port) for i in ports_list]), 
            isudp=','.join([('1' if p.trans_type==TransType.UDP else '0') for p in ports_list]), timeout=connect_timeout), 30, True)
        if ret is None:
            logger.error(f"{ip}端口扫描错误!"+' '*20)
            return result, len(ports_list)
        ret = json.loads(ret)
        if ret:
            for p, response in ret.items():
                for port in ports_list:
                    if port.port == int(p):
                        port.response = base64.b64decode(response.encode())
                        self._update_port_note_by_response(port)
                        result.append(port)
                        p = colour.colorize(str(p).rjust(5), 'bold', 'yellow')
                        logger.info(f"{ip}开放了{port.trans_type.name}端口{p}!"+' '*20, True)
                        break
        return result, len(ports_list)

    def port_scan(self, ip:str, connect_timeout:int, ports_map:ServicePortMap, threads: int)->ServicePortMap:
        """对指定IP进行端口扫描

        Args:
            ip (str): 指定IP地址
            connect_timeout (int): 连接超时时间
            ports_map (ServicePortMap): 端口列表
            threads (int): 扫描线程数量

        Returns:
            ServicePortMap: 返回开放的端口列表
        """
        logger.info(f"开始扫描`{ip}`的端口...")
        ret = ServicePortMap()
        block_ports = []
        ports = ports_map.port_list
        for i in range(0, len(ports), 10):#每次检测10个端口
            block_ports.append(ports[i:i+10])
        job = Worker(self._port_scan_handler, block_ports, threads)
        job.set_param(ip, connect_timeout)
        job.start()
        try:
            while job.is_running():
                workdone_count = 0
                opened_count = 0
                for v in job.current_vlist:
                    if v.solved:
                        opened_count += len(v.ret[0])
                        workdone_count += v.ret[1]
                per = int(workdone_count/len(ports)*100)
                print(f"端口扫描进度 {per}% ({workdone_count}/{len(ports)}), {ip}开放了{opened_count}个端口.", end='\r' if workdone_count<len(ports) else '\n', 
                    flush=True)
                time.sleep(0.3)
        except BaseException as e:
            if isinstance(e, KeyboardInterrupt):
                logger.info("正在暂停扫描进程..."+' '*60)
            job.stop()
            logger.warning("端口扫描停止!")

        for v in job.current_vlist:# 线程结束后统计
            if v.solved:
                ret.add_from_list(v.ret[0])
        logger.info(f"端口扫描完毕, {ip}一共开放了`{len(ret.port_list)}`个端口."+' '*20)
        return ret

    def _host_survival_scan_handler_by_udp(self, ip_list:list, timeout:int)-> tuple:
        '''使用UDP探测主机是否存活
        '''
        result = []
        ret = self.session.evalfile('host_scan', dict(hosts=','.join(ip_list), timeout=timeout), 0, True)
        if ret is None:
            logger.error(f"UDP主机扫描错误！"+' '*30)
            return result, len(ip_list)
        ret = json.loads(ret)
        for ip in ret:
            result.append(ip)
            ip = colour.colorize(ip.ljust(15), 'bold', 'yellow')
            logger.info(f"{ip} 存活!"+' '*20, True)
        return result, len(ip_list)

    def _host_survival_scan_handler_by_ping(self, ip_list:list, timeout:int)-> tuple:
        '''使用ping命令探测主机是否存活
        '''
        result = []
        ret = b''
        if self.session.server_info.os_type == OSType.WINDOWS:
            ips = ','.join(ip_list)
            ret = self.session.exec(f'cmd /c "for %i in ({ips}) do ping -n 1 -w {timeout} %i && echo %iok"'.encode(), 0)
        else:
            ips = ' '.join(ip_list)
            ret = self.session.exec(f'for ip in {ips};do ping -c 1 -W {timeout//1000} $ip && echo $ip"ok";done'.encode(), 0)

        if ret is None:
            logger.error("PING扫描发生错误!")
            return result, len(ip_list)
            
        ret = re.findall(r'^\s*(\d+\.\d+\.\d+\.\d+)ok\s*$', ret.decode(errors='ignore'), re.M)
        for ip in ret:
            result.append(ip)
            ip = colour.colorize(ip.ljust(15), 'bold', 'yellow')
            logger.info(f"{ip} 存活!"+' '*20, True)
        return result, len(ip_list)

    def host_survival_scan(self, hosts:List[str], timeout:int, threads:int, host_detect_udp: bool)->List[str]:
        """测试主机是否存活

        Args:
            hosts (List[str]): 主机ip地址列表
            timeout (int): 扫描超时时间，单位毫秒
            threads (int): 扫描线程数量
            host_detect_udp (bool): 是否使用UDP进行主机存活检测

        Returns:
            List[str]: 返回存活的主机列表
        """
        ret = []
        if not host_detect_udp:# 若使用ping扫描，则检查是否有ping命令使用权限
            tmp = b''
            if self.session.server_info.os_type == OSType.WINDOWS:
                tmp = self.session.exec(f'cmd /c "ping -n 1 -w {timeout} 127.0.0.1 && echo pingok"'.encode())
            else:
                tmp = self.session.exec(f'ping -c 1 -W {timeout//1000} 127.0.0.1 && echo pingok'.encode())
            if tmp and b'pingok' in tmp:
                logger.info("远程主机拥有PING权限!")
            else:
                logger.error("远程主机无法执行ping命令，可能权限不够或者不存在ping命令")
                return ret
        block_hosts = []
        for i in range(0, len(hosts), 10):#每次检测10个主机
            block_hosts.append(hosts[i:i+10])
        job = Worker(self._host_survival_scan_handler_by_ping if not host_detect_udp else self._host_survival_scan_handler_by_udp, block_hosts, threads)
        job.set_param(timeout)
        job.start()
        try:
            while job.is_running():
                workdone_count = 0
                alive_count = 0
                for v in job.current_vlist:
                    if v.solved:
                        alive_count += len(v.ret[0])
                        workdone_count += v.ret[1]
                per = int(workdone_count/len(hosts)*100)
                print(f"进度 {per}% ({workdone_count}/{len(hosts)}), {alive_count}个存活主机.", end='\r' if workdone_count<len(hosts) else '\n', flush=True)
                time.sleep(0.3)
        except:
            job.stop()
            logger.warning("扫描停止!")
        
        for v in job.current_vlist:# 线程结束后统计
            for ip in v.ret[0]:
                ret.append(ip)
        logger.info(f"主机存活扫描完毕, 一共`{len(ret)}`个存活")
        return ret

    def docomplete(self, text: str)-> List[str]:
        result = []
        match = re.fullmatch(r'(%s +)(\w*)'%self.command_name, text)
        if match:
            for key in ['scan', 'report']:
                if key.startswith(match.group(2).lower()):
                    result.append(match.group(1)+key+' ')
        return result