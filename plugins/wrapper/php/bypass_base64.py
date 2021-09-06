
from api import Session, Wrapper, Plugin, SessionType

base64_code = r'''
class Base64{
    private $_base64hash = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'; /*这是Base64编码使用的标准字典*/
    private $_DecodeTable = array( /* 这是php源码中使用的解码表,包含了256个字符对应的编码 */
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -1, -1, -2, -2, -1, -2, -2,
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
        -1, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, 62, -2, -2, -2, 63,
        52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -2, -2, -2, -2, -2, -2,
        -2,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14,
        15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -2, -2, -2, -2, -2,
        -2, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
        41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -2, -2, -2, -2, -2,
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
        -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2
    );
    private $_encode_data = 0xfc0000;
    private $_debug       = false;
    private $_encode_result = '';
    public function encode($str) {
        $len = strlen($str);
        $num = 0;
        $bin = 0;
        $arr = array();
        if($len >= 3) {
            for($i=0;$i<$len;$i++) {
                $bin = $bin << 8;
                if($this->_debug) {
                    echo '$bin = ',decbin($bin),"\n";
                    echo 'binary = ', decbin(ord($str[$i])),"\n";
                }
                $bin = $bin | ord($str{$i});
                if(($i+1)%3 == 0) {
                    $this->_encode_func($bin,3);
                    $bin = 0;
                }
            }
        }
        if($len%3 == 1) {
            $bin = ord($str[$len-1]);
            $bin = $bin << 4;
            $this->_encode_func($bin,1);
            $this->_encode_result .= '==';
        } else if($len%3 == 2) {
            $bin = ord($str[$len-2]);
            $bin = $bin << 8;
            $bin = $bin | ord($str[$len-1]);
            $bin = $bin << 2;
            $this->_encode_func($bin,2);
            $this->_encode_result .= '=';
        }
        return $this->_encode_result;
    }
    private function _encode_func($bin,$bytes = 3) {
        $num = 3;
        $matches = 0;
        $bits1 = ($num - $bytes) * 6;
        $bits2 = $bytes * 6;
        $matches = $this->_encode_data >> $bits1;
        while( $matches ) {
            $result = $bin & $matches;
            $result = $result >> $bits2;
            $bytes--;
            $bits1 = ($num - $bytes) * 6;
            $bits2 = $bytes * 6;
            $matches = $this->_encode_data >> $bits1;
            if($this->_debug) {
                echo '$result = ',$result,' binary = ',decbin($result),"\n";
            }
            $this->_encode_result .= $this->_base64hash[$result];
        }
    }
    public function decode($str) {
        $bin = 0;
        $length = strlen($str)-1;
        $_decode_result = '';
        $len = 0;
        $i = 0;
        while( ($len <= $length) ) {
            $ch = $str[$len++];
            if ($ch == '=') {
                if ($len<=$length && $str[$len] != '=' && (($i % 4) == 1)) {
                    return NULL;
                }
                continue;
            }
            $ch = $this->_DecodeTable[ord($ch)];
            // 下面这连个条件，只有 ch < 0 会起作用，ch == -2 永远不会起作用，即所有不合法的字符均跳过。
            if ($ch < 0 || $ch == -1) { /* a space or some other separator character, we simply skip over */
                continue;
            } else if ($ch == -2) {
                return NULL;
            }
            switch($i % 4) {
                case 0:
                    $bin = intval($ch) << 2;
                    break;
                case 1:
                    $bin = intval($bin) | intval($ch) >> 4;
                    $_decode_result .= chr($bin);
                    $bin = ( intval($ch) & 0x0f ) << 4;
                    break;
                case 2:
                    $bin = intval($bin) | intval($ch) >> 2;
                    $_decode_result .= chr($bin);
                    $bin = ( intval($ch) & 0x03 ) << 6;
                    break;
                case 3:
                    $bin = intval($bin) | intval($ch);
                    $_decode_result .= chr($bin);
                    break;
            }
            $i++;
        }
        return $_decode_result;
    }
    public function debug($open = true) {
        $this->_debug = $open;
    }
}
function be($str){$b=new Base64();return $b->encode($str);}
function bd($str){$b=new Base64();return $b->decode($str);}
'''

def get_plugin_class():
    return BypassBase64Wrapper

class BypassBase64Wrapper(Plugin, Wrapper):
    name = "绕过系统对base64编码函数的禁用"
    description = "通过替换base64_encode和base64_decode的实现来绕过系统对base64编码函数的禁用"
    supported_session_types = [SessionType.PHP]

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def wrap(self, payload: bytes) -> bytes:
        if b'base64_encode(' in payload or b'base64_decode(' in payload:
            payload = payload.replace(b'base64_encode(', b'be(').replace(b'base64_decode(', b'bd(')
            payload = base64_code.encode()+payload
        return payload