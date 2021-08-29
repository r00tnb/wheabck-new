<?php
//global: $pwd, $path
function perm($file){
    if(is_link($file)){
        return "lrwxrwxrwx";
    }
    $perms = fileperms($file);
    if (($perms & 0xC000) == 0xC000) {
        // Socket
        $info = 's';
    } elseif (($perms & 0xA000) == 0xA000) {
        // Symbolic Link
        $info = 'l';
    } elseif (($perms & 0x8000) == 0x8000) {
        // Regular
        $info = '-';
    } elseif (($perms & 0x6000) == 0x6000) {
        // Block special
        $info = 'b';
    } elseif (($perms & 0x4000) == 0x4000) {
        // Directory
        $info = 'd';
    } elseif (($perms & 0x2000) == 0x2000) {
        // Character special
        $info = 'c';
    } elseif (($perms & 0x1000) == 0x1000) {
        // FIFO pipe
        $info = 'p';
    } else {
        // Unknown
        $info = 'u';
    }
    
    // Owner
    $info .= (($perms & 0x0100) ? 'r' : '-');
    $info .= (($perms & 0x0080) ? 'w' : '-');
    $info .= (($perms & 0x0040) ?
                (($perms & 0x0800) ? 's' : 'x' ) :
                (($perms & 0x0800) ? 'S' : '-'));
    
    // Group
    $info .= (($perms & 0x0020) ? 'r' : '-');
    $info .= (($perms & 0x0010) ? 'w' : '-');
    $info .= (($perms & 0x0008) ?
                (($perms & 0x0400) ? 's' : 'x' ) :
                (($perms & 0x0400) ? 'S' : '-'));
    
    // World
    $info .= (($perms & 0x0004) ? 'r' : '-');
    $info .= (($perms & 0x0002) ? 'w' : '-');
    $info .= (($perms & 0x0001) ?
                (($perms & 0x0200) ? 't' : 'x' ) :
                (($perms & 0x0200) ? 'T' : '-'));
    
    return $info;
}
function getsize($file){
    if(is_file($file)){
        return filesize($file);
    }elseif(is_dir($file) && is_readable($file)){
        $r = scandir($file);
        $size = 0;
        foreach($r as $name){
            if($name == '.' || $name == "..") continue;
            if(is_file($file.DIRECTORY_SEPARATOR.$name))
                $size += filesize($file.DIRECTORY_SEPARATOR.$name);
        }
        return $size;
    }
    return 0;
}
function info($file){
    $r = array();
    $r[0] = perm($file);
    if(strpos(strtoupper(PHP_OS), "WIN")===false){
        $r[1] = posix_getpwuid(fileowner($file))['name'];
        $r[2] = posix_getgrgid(filegroup($file))['name'];
    }else{
        $r[1] = getenv('USERNAME');
        $r[2] = getenv('USERNAME');
    }
    $r[3] = getsize($file);
    $r[4] = filemtime($file);
    if(is_link($file)){
        $tmp = readlink($file);
        $file = basename($file)." -> ".$tmp;
        $r[5] = base64_encode($file);
    }else
        $r[5] = base64_encode(basename($file));
    return $r;
}

function run($vars){
    extract($vars);
    chdir($pwd);
    $ret = array('code'=>1, 'msg'=>array());
    if(is_dir($path)){
        if(is_readable($path)){
            $r = scandir($path);
            foreach($r as $name){
                if($name == '.' || $name == "..") continue;
                $ret['msg'][] = info($path.DIRECTORY_SEPARATOR.$name);
            }
        }else{
            $ret['code'] = -2;
        }
    }else if(is_file($path)){
        $ret['msg'][] = info($path);
    }else{
        $ret['code'] = -1;
    }
    return json_encode($ret);
}