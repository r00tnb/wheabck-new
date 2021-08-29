from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, SessionType, Session, PHPPayload, logger
import argparse, webbrowser, tempfile, os

from urllib.parse import urlparse

def get_plugin_class():
    return PHPInfo

class PHPInfo(Plugin, Command):
    name = "phpinfo"
    description = "获取phpinfo的信息，可在终端或浏览器中查看"
    supported_session_types = [SessionType.PHP]

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.name, description=self.description)
        self.parse.add_argument('-v', '--view', help="使用默认浏览器查看phpinfo信息", 
            action='store_true')
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    @property
    def command_name(self) -> str:
        return self.name

    @property
    def command_type(self) -> CommandType:
        return CommandType.MISC_COMMAND

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
            urlinfo = urlparse(self.session.options.get_option('target'))
            fname = f"{urlinfo.netloc}_phpinfo.html"
            with tempfile.TemporaryDirectory() as tmpdir:
                path = os.path.join(tmpdir, fname)
                with open(path, 'wb') as f:
                    f.write(data)
                path = os.path.abspath(path)
                logger.info(f"在默认浏览器中查看phpinfo,路径`{path}`")
                if not webbrowser.open(f"file://{path}"):
                    logger.error(f"浏览器查看失败！")
                    return CommandReturnCode.FAIL
        else:#终端查看
            print('未实现终端查看！')
        return CommandReturnCode.SUCCESS