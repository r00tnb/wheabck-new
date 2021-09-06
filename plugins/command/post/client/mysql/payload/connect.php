<?php
//global: $host, $user, $password, $database, $port


function run($vars){
    extract($vars);
    $ret = array('code'=>0, 'msg'=>'');
    if(function_exists('mysqli_connect')){
        $conn = @mysqli_connect($host, $user, $password, $database, $port);
        if(!$conn){
            $ret['code'] = -1;
            $ret['msg'] = 'Connect failed: '.mysqli_connect_error();
            $ret['msg'] = base64_encode($ret['msg']);
        }else{
            $ret['code'] = 1;
            @mysqli_kill($conn, mysqli_thread_id($conn));
            @mysqli_close($conn);
        }
    }
    return json_encode($ret);
}