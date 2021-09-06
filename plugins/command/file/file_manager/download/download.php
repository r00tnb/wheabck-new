<?php
//global: $pwd, $path

function run($vars){
    extract($vars);
    $ret = array('code'=>0, 'msg'=>'');
    chdir($pwd);
    if(file_exists($path)){
        if(is_file($path)){
            if(is_readable($path)){
                $f = fopen($path, 'rb');
                $data = fread($f, filesize($path));
                $ret['msg'] = base64_encode($data);
                $ret['code'] = 1;
            }else
                $ret['code'] = 2;
        }elseif(is_dir($path)){
            if(is_readable($path)){
                $ret['code'] = -3;
                $ret['msg'] = DIRECTORY_SEPARATOR;
            }else
                $ret['code'] = -1;
        }else{
            $ret['code'] = -2;
        }
    }
    return json_encode($ret);
}