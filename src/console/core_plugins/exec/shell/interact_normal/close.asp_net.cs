using System;
using System.Web;
using System.IO;
using System.Text;
using System.Threading;
using System.Runtime.Serialization;

public class Payload{
    public static string run(){
        Directory.SetCurrentDirectory(Globals.pwd);
        Mutex mut = new Mutex(false, "test123");
        mut.WaitOne();
        if(File.Exists(Globals.infile)){
            File.Delete(Globals.infile);
        }
        if(File.Exists(Globals.outfile)){
            File.Delete(Globals.outfile);
        }
        mut.ReleaseMutex();
        return "";
    }
}