<?php
//global: $pwd, $file, $atime, $mtime

function run($vars){
    extract($vars);
    chdir($pwd);
    if($atime === null) $atime = time();
    if($mtime === null) $mtime = time();
    if(touch($file, $mtime, $atime) === false) return "-1";
    return "1";
}