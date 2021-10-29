<?php
/**
 * $htdir 要覆盖的.htaccess文件所在目录
 * $htdata .htaccess数据
 * $cmdpath 要删除的cmd文件路径
 */
function run($vars){
    extract($vars);
    $htpath = $htdir+DIRECTORY_SEPARATOR+'.htaccess';
    if($htpath != '' and is_file($htpath)){
        if(strlen($htdata)>0){
            $f = fopen($htpath, 'wb');
            fwrite($f, $htdata);
            fclose($f);
        }else{
            @unlink($htpath);
        }
    }
    @unlink($cmdpath);

    return "1";
}