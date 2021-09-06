<?php
//global: $pwd, $path

function run($vars){
    extract($vars);
    $ret = array('code'=>1, 'msg'=>"");
    chdir($pwd);
    if(!chdir($path)){
        $ret['code'] = -1;//failed
        $ret['msg'] = base64_encode(error_get_last()['message']);
    }else{
        $ret['msg'] = base64_encode(getcwd());
    }
    return json_encode($ret);
}