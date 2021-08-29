<?php
//global: $pwd, $source, $dest, $f

function run($vars){
    extract($vars);
    if(chdir($pwd)){
        if(!file_exists($source)){
            return "Souce file not exists!";
        }
        if(file_exists($dest) && !$f){
            return "Dest file exists";
        }
        if(copy($source, $dest)){
            return "ok";
        }
    }
}