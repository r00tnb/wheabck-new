<?php
//global: $shost, $sport, ($type, $rhost, $rport connect独有), $sockid, （$data write独有） , $action

function run($vars){
    extract($vars);
    $ret = array('code'=>-1, 'msg'=>'');
    $rhost = gethostbyname($rhost); // 防止客户端解析失败
    if(($sock=stream_socket_client("udp://[$shost]:$sport", $errno, $errstr))!==false){
        $buf = '';
        switch($action){
            case 1:
                $buf = pack('CCn', 1, $type, $type == 4?6:18);
                stream_socket_sendto($sock, $buf);
                stream_socket_sendto($sock, inet_pton($rhost).pack('n', $rport));
                break;
            case 2:
                $buf = pack('CCn', 2, $sockid, 0);
                stream_socket_sendto($sock, $buf);
                break;
            case 3:
                $buf = pack('CCn', 3, $sockid, strlen($data));
                stream_socket_sendto($sock, $buf);
                stream_socket_sendto($sock, $data);
                break;
            case 4:
                $buf = pack('CCn', 4, $sockid, 0);
                stream_socket_sendto($sock, $buf);
                break;
        }
        if(($recvbuf = stream_socket_recvfrom($sock, 3))!==false){
            $code = unpack('C', substr($recvbuf, 0, 1))[1];
            $length = unpack('n', substr($recvbuf, 1, 2))[1];
            if($code == 0){
                switch($action){
                    case 1:
                        if(($recvbuf = stream_socket_recvfrom($sock, 1))!==false){
                            $ret['code'] = 1;
                            $ret['msg'] = unpack('C', $recvbuf)[1];
                        }
                        break;
                    case 2:
                        if(($recvbuf = stream_socket_recvfrom($sock, $length))!==false){
                            $ret['code'] = 1;
                            $ret['msg'] = base64_encode($recvbuf);
                        }
                        break;
                    case 3:
                    case 4:
                        $ret['code'] = 1;
                        break;
                }
            }else{
                $ret['code'] = -2;
                $ret['msg'] = $code;
            }
        }
    }
    if($ret['code'] === -1){
        $ret['msg'] = base64_encode(socket_strerror(socket_last_error()));
    }
    return json_encode($ret);
}
