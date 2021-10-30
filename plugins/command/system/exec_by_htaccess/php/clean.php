<?php
/**
 * $htdir 要覆盖的.htaccess文件所在目录
 * $htdata .htaccess数据
 * $cmddir 命令文件所在目录
 * $suffix 命令文件后缀
 */
function run($vars){
    extract($vars);
    // 重置htaccess文件
    $htpath = $htdir.DIRECTORY_SEPARATOR.'.htaccess';
    if(is_file($htpath)){
        if(strlen($htdata)>0){
            $f = fopen($htpath, 'wb');
            fwrite($f, $htdata);
            fclose($f);
        }else{
            @unlink($htpath);
        }
    }

    // 删除所有命令文件
    if(is_dir($cmddir)){
        $dh  = opendir($cmddir);
        while (false !== ($filename = readdir($dh))) {
            if($filename !=".." && $filename !="."){
                $path = $cmddir.DIRECTORY_SEPARATOR.$filename;
                if(is_file($path)){
                    $l = strlen(($suffix))+1;
                    if(substr($filename, -$l) === '.'.$suffix){
                        @unlink($path);
                    }
                }
            }

        }
        closedir($dh);
    }

    return "1";
}