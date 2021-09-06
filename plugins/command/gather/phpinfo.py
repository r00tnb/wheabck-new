from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, SessionType, Session, PHPPayload, logger
import argparse, webbrowser, tempfile, os
import http.server, threading, time

from urllib.parse import urlparse

def get_plugin_class():
    return PHPInfo

class PHPInfo(Plugin, Command):
    name = "phpinfo"
    description = "获取phpinfo的信息，可在终端或浏览器中查看"
    supported_session_types = [SessionType.PHP]
    command_name = "phpinfo"
    command_type = CommandType.GATHER_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('-v', '--view', help="使用默认浏览器查看phpinfo信息", 
            action='store_true')
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)


    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if not args.view:
            print('未实现终端查看！')
            return CommandReturnCode.FAIL
        payload_str = r'''
        function run($vars){
            ob_start();
            phpinfo();
            $result = ob_get_contents();
            ob_end_clean();
            return $result;
        }
        '''
        payload = PHPPayload(payload_str.encode())
        data = self.session.eval(payload)
        if data is None:
            logger.error("phpinfo信息获取失败！")
            return CommandReturnCode.FAIL

        if args.view:#浏览器查看
            return self.view_in_browser(data)
        else:#终端查看
            print('未实现终端查看！')
        return CommandReturnCode.SUCCESS

    def view_in_browser(self, data:bytes)->CommandReturnCode:
        urlinfo = urlparse(self.session.options.get_option('target').value)
        fname = f"{urlinfo.netloc}_phpinfo.html"
        addr = ['localhost', 8080]
        class HttpHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(data)
                self.close_connection = True
        class OpenWeb(threading.Thread):
            def __init__(self, path:str, server):
                super().__init__()
                self.path = path
                self.server = server
                self.retcode = CommandReturnCode.SUCCESS
            def run(self) -> None:
                time.sleep(1)
                if not webbrowser.open(self.path):
                    logger.error(f"浏览器查看失败！")
                    self.retcode = CommandReturnCode.FAIL
                time.sleep(1)
                self.server.shutdown()
        for i in range(10):
            try:
                server = http.server.HTTPServer(tuple(addr), HttpHandler)
            except BaseException as e:
                addr[1] += 1
            else:
                path = f"http://{addr[0]}:{addr[1]}/{fname}"
                logger.info(f"在默认浏览器中查看phpinfo,路径`{path}`")
                t = OpenWeb(path, server)
                t.setDaemon(True)
                t.start()
                server.serve_forever()
                t.join(1)
                return t.retcode
        logger.error("没有合适的端口！")
        return CommandReturnCode.FAIL
