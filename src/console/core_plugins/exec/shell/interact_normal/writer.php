<?php
//global: $infile, $pwd, $cmd

function run($vars){
    extract($vars);
    chdir($pwd);
    if(file_exists($infile)){
        $in = fopen($infile, "wb");
        flock($in, LOCK_EX);
        fwrite($in, $cmd);
        flock($in, LOCK_UN);
        fclose($in);
    }else{
        return "-1";
    }
    return "1";
}