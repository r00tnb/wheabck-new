<?php
/**
 * $cmdpath cgi文件路径 (绝对路径)
 * $cmddata cgi文件内容
 */

function write_file($path, $data){
    $f = fopen($path, 'ab');
    fwrite($f, $data);
    fclose($f);
}

function run($vars){
    extract($vars);

    // 写命令文件
    $dir = dirname($cmdpath);
    if(!is_writable($dir)) return '-1';
    else{
        $f = fopen($cmdpath, 'wb');
        fwrite($f, $cmddata);
        fclose($f);
        @chmod($cmdpath, 0777);
    }
    
    return "0";
}