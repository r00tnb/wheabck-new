<?php
//global: $pwd, $path

function run($vars){
    extract($vars);
    $ret = array('code'=>0, 'msg'=>'');
    chdir($pwd);
    if(is_file($path)){
        if(is_readable($path)){
            $f = fopen($path, 'rb');
            $ret['msg'] = base64_encode(fread($f, filesize($path)));
            $ret['code'] = 1;
        }else{
            $ret['code'] = -1;
        }
    }
    return json_encode($ret);
}