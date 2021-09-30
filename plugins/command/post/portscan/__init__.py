from typing import Any, Dict, List, Tuple
from api import Session, logger, colour, tablor, Plugin, Command, CommandReturnCode, CommandType, Cmdline
import argparse
import re
import socket
import struct
import os
import csv
import json
import threading
import math
import base64
from .worker import Worker
import enum

def get_plugin_class():
    return PortScanPlugin

class  TransType(enum.Enum):
    TCP = 1
    UDP = 2
    UNKNOWN = 3

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
        self.trans_type = type # 传输协议类型
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
        self.service_list:List[Port] = [] # 存储端口信息
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
                    self.service_list.append(Port(port, TransType.from_name(t), service, note))
                except:
                    logger.error(f"加载第`{reader.line_num}`行失败!")



class PortScanPlugin(Plugin, Command):
    name = "端口扫描"
    description = "通过webshell进行端口扫描"
    command_name = 'portscan'
    command_type = CommandType.POST_COMMAND

    default_ports = ServicePortMap() # 默认要扫描的端口列表
    
    def __init__(self):
        super().__init__()
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        sub_parses = self.parse.add_subparsers()
        report_parse = sub_parses.add_parser("report", help="查看扫描报告")
        report_parse.add_argument('-l', '--list', help="列出所有报告", action='store_true')
        report_parse.add_argument('-v', '--view', help="查看指定报告ID的报告内容")
        report_parse.add_argument('-d', '--delete', help="删除指定ID的报告")

        scan_parse = sub_parses.add_parser('scan', help="进行端口扫描")
        scan_parse.add_argument('-n', '--nodetect', help="不进行主机存活检查.", action="store_true")
        scan_parse.add_argument('-U', '--host-detect-udp', help="使用UDP检查主机是否存活（不准确），当没有足够权限时可尝试该方法", action="store_true")
        scan_parse.add_argument('-T', '--type', help="指定要检查的端口传输协议类型，默认检查所有类型", choices=[t.name for t in TransType])
        scan_parse.add_argument('-p', '--ports', help="指定要扫描的端口（不指定该参数则扫描默认端口），如：1-65535， 1433 22等.", nargs='+')
        scan_parse.add_argument('-t', '--threads', help="指定扫描的线程数量（默认一个线程）.", default=1, type=int)
        scan_parse.add_argument('--timeout', help="指定等待端口响应的超时时间，单位毫秒（默认1000 ms）.", default=1000, type=int)
        scan_parse.add_argument('hosts', help="指定要扫描的主机，如192.168.1.1/24, 192.168.1.10-192.168.1.100, 192.168.1.2,...", nargs='+')
        self.help_info = self.parse.format_help()

    def run(self, args: Cmdline)-> int:
        args = self.parse.parse_args(args.options)
        if args.result:
            self.show_last_result()
            return self.SUCCESS
        
        hosts = self._parse_hosts(args.hosts)
        if not hosts:
            logger.error("No host list!")
            return self.STOP

        self._scan_result = {}
        logger.info(f"Threads count `{args.threads}`")
        if args.nodetect:
            logger.info("Not proceed alive host detection!")
        else:
            logger.info(f"Proceed alive host detection, use `{'UDP' if args.host_detect_udp else 'PING'}` method.")
        logger.info(f"{'Not proceed' if args.udp is None and args.tcp is None else 'Proceed'} {'`UDP`' if args.udp is not None else ''} {'`TCP`' if args.tcp is not None else ''} port scan.")
        if not args.nodetect:# 主机存活检测
            self.host_survival_scan(hosts, args.timeout, args.threads, args.host_detect_udp)
            hosts = [ip for ip in self._scan_result]
            print('')
        if args.tcp is not None:
            tcp_ports = self._parse_ports(args.tcp)
            for ip in hosts:
                self.port_scan(ip, args.timeout, tcp_ports, False, args.threads)
                print('')
        if args.udp is not None:
            udp_ports = self._parse_ports(args.udp, True)
            for ip in hosts:
                self.port_scan(ip, args.timeout, udp_ports, True, args.threads)
                print('')

        self.show_last_result()
        return self.SUCCESS
        
    def _parse_ports(self, ports:list, isudp=False)->list:
        '''解析端口范围，返回端口列表
        '''
        ret = []
        default_ports = self.default_udp_ports if isudp else self.default_tcp_ports
        if not ports:
            return default_ports
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
                    pp = Port(port, Port.UDP if isudp else Port.TCP, '')
                    tmp = [t for t in default_ports if t.port==pp.port]
                    if tmp:
                        pp = tmp[0]
                    ret.append(pp)
            except:
                logger.error(f"Port `{p}` format error!")
        return ret


    def _parse_hosts(self, hosts:list)->list:
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
        
    def show_last_result(self):
        if self._scan_result:
            hosts = [['Host', 'Opened Ports Count']]
            ports_list = []
            for ip in self._scan_result:
                hosts.append([ip, len(self._scan_result[ip])])
                ports = {'ip':ip, 'ports':[['Port', 'Note']]}
                for p in self._scan_result[ip]:
                    ports['ports'].append([f"{p.port}/{p.type}", p.note])
                ports_list.append(ports)
            print(tablor(hosts, border=False, title="Alive Host"))
            for p in ports_list:
                if len(p['ports']) > 1:
                    print(tablor(p['ports'], border=False, title=p['ip']))
            return
        print(colour.colorize('No scan result info!', ['bold', 'note'], 'red'))

    def _update_port_note_by_response(self, port:Port):
        '''根据响应修改端口的说明
        '''
        if port.note:# 有默认说明的暂时不识别
            return
        if not port.response:
            return
        text = port.response.decode(self.session.client.options.encoding, 'ignore')
        if re.match(r'(?i)HTTP/\d+\.\d+ \d+ .*\r\n', text):
            port.note = "http"
        elif re.match(r'(?i)SSH-', text):
            port.note = "ssh"
        else:
            port.note = f"Unknown service[{text[:50].strip()}]"

    def _port_scan_handler(self, ports_list:list, ip:str, connect_timeout:int, isudp: bool)-> tuple:
        '''端口扫描处理函数
        '''
        result = []
        self.session.client.options.set_temp_option('timeout', 30)
        self.session.client.options.set_temp_option('verbose', 1)
        ret = self.evalfile("payload/port_scan", ip=ip, ports=','.join([str(i.port) for i in ports_list]), isudp=isudp, timeout=connect_timeout)
        ret = ret.data
        if ret is None:
            logger.error(f"Scan {'UDP' if isudp else 'TCP'} port on {ip} error!"+' '*20)
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
                        logger.info(f"{'UDP' if isudp else 'TCP'} port {p} is opened on {ip}!"+' '*20, True)
                        break
        return result, len(ports_list)

    def port_scan(self, ip:str, connect_timeout:int, ports:list, isudp: bool, threads: int):
        logger.info(f"Start {'UDP' if isudp else 'TCP'} port scan on {ip}...")
        block_ports = []
        for i in range(0, len(ports), 10):#每次检测10个端口
            block_ports.append(ports[i:i+10])
        job = Worker(self._port_scan_handler, block_ports, threads)
        job.set_param(ip, connect_timeout, isudp)
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
                print(f"Progress {per}% ({workdone_count}/{len(ports)}), {opened_count} opened ports on {ip}.", end='\r', flush=True)
                utils.sleep(0.3)
        except:
            job.stop()
            logger.warning("Work is over!")

        for v in job.current_vlist:# 线程结束后统计
            if self._scan_result.get(ip) is None:
                self._scan_result[ip] = []
            self._scan_result[ip].extend(v.ret[0])
        logger.info(f"All {'UDP' if isudp else 'TCP'} ports have been detected, total `{len(self._scan_result[ip])}` opened on {ip}."+' '*20)

    def _host_survival_scan_handler_by_udp(self, ip_list:list, timeout:int)-> tuple:
        '''使用UDP探测主机是否存活
        '''
        result = []
        self.session.client.options.set_temp_option('timeout', 0)
        self.session.client.options.set_temp_option('verbose', 1)
        ret = self.evalfile('payload/host_scan', hosts=','.join(ip_list), timeout=timeout)
        if not ret.is_success():
            logger.error(f"Scan host error!"+' '*30)
            return result, len(ip_list)
        ret = ret.data
        ret = json.loads(ret)
        for ip in ret:
            result.append(ip)
            ip = colour.colorize(ip.ljust(15), 'bold', 'yellow')
            logger.info(f"{ip} is alive!"+' '*20, True)
        return result, len(ip_list)

    def _host_survival_scan_handler_by_ping(self, ip_list:list, timeout:int)-> tuple:
        '''使用ping命令探测主机是否存活
        '''
        result = []
        ret = ''
        if self.session.server_info.isWindows():
            ips = ','.join(ip_list)
            self.session.client.options.set_temp_option('timeout', 0)
            ret = self.exec_command(f'cmd /c "for %i in ({ips}) do ping -n 1 -w {timeout} %i && echo %iok"')
        else:
            ips = ' '.join(ip_list)
            self.session.client.options.set_temp_option('timeout', 0)
            ret = self.exec_command(f'for ip in {ips};do ping -c 1 -W {timeout//1000} $ip && echo $ip"ok";done')

        if ret is None:
            logger.error("host_survival_scan_handler_by_ping error!")
            return result, len(ip_list)
            
        ret = re.findall(r'^\s*(\d+\.\d+\.\d+\.\d+)ok\s*$', ret, re.M)
        for ip in ret:
            result.append(ip)
            ip = colour.colorize(ip.ljust(15), 'bold', 'yellow')
            logger.info(f"{ip} is alive!"+' '*20, True)
        return result, len(ip_list)

    def host_survival_scan(self, hosts:str, timeout:int, threads:int, host_detect_udp: bool):
        '''测试主机是否存活，timeout超时时间，单位毫秒
        '''
        logger.info("Start host survival detection...")
        if not host_detect_udp:# 若使用ping扫描，则检查是否有ping命令使用权限
            ret = None
            if self.session.server_info.isWindows():
                ret = self.exec_command(f'cmd /c "ping -n 1 -w {timeout} 127.0.0.1 && echo pingok"')
            else:
                ret = self.exec_command(f'ping -c 1 -W {timeout//1000} 127.0.0.1 && echo pingok')
            if ret is not None and 'pingok' in ret:
                logger.info("Ping scan is currently available!")
            else:
                logger.error("Currently, there is no permission to use ping command, or ping command does not exist!")
                return
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
                print(f"Progress {per}% ({workdone_count}/{len(hosts)}), {alive_count} alive hosts.", end='\r', flush=True)
                utils.sleep(0.3)
        except:
            job.stop()
            logger.warning("Work is over!")
        
        for v in job.current_vlist:# 线程结束后统计
            for ip in v.ret[0]:
                self._scan_result[ip] = []
        logger.info(f"All hosts have been detected, total `{len(self._scan_result)}` alive."+' '*20)


    def hook_loaded(self):
        config = self.load_config('portscan-last-result')
        if config is None:
            return
        
        self._scan_result = {}
        for ip, ports in config.items():
            self._scan_result[ip] = [Port.from_json(p) for p in ports]

    def hook_destroy(self):
        config = {}
        for ip, ports in self._scan_result.items():
            config[ip] = [Port.to_json(p) for p in ports]
        self.save_config('portscan-last-result', config)

exploit.load_default_ports()