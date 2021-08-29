<?php
//global: $pwd, $path

function run($vars){
    extract($vars);
    $ret = array('msg'=>'', 'code'=>0);
    chdir($pwd);
    if(file_exists($path)){
        if(!is_writable($path)){
            $ret['code'] = -2;
        }elseif(is_readable($path)){
            $f = fopen($path, 'rb');
            $ret['msg'] = base64_encode(fread($f, filesize($path)));
            $ret['code'] = 1;
            fclose($f);
        }else{
            $ret['code'] = -1;
        }
    }
    return json_encode($ret);
}