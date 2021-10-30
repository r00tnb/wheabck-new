<?php
/**
 * $htdata htaccess数据
 * $htdir htaccess目录(绝对路径)
 */

function write_file($path, $data){
    $f = fopen($path, 'ab');
    fwrite($f, $data);
    fclose($f);
}

function run($vars){
    extract($vars);
    $ret = array('code'=>0, 'msg'=>'');
    // 写.htaccess文件
    $path = $htdir.DIRECTORY_SEPARATOR.'.htaccess';
    if(is_file($path)){
        if(is_readable($path)){
            $ret['code'] = 1;
            $f = fopen($path, 'rb');
            $ret['msg'] = base64_encode(fread($f, filesize($path)));
            fclose($f);
        }else $ret['code'] = -1;

        if(!is_writable($path)){
            $ret['code'] =  -2;
            return json_encode($ret);
        }

        write_file($path, $htdata);
    }else{
        if(is_writable($htdir)){
            write_file($path, $htdata);
        }else $ret['code'] = -3;
    }
    
    return json_encode($ret);
}