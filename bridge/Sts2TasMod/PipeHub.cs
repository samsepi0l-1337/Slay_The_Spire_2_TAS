using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using Godot;

namespace Sts2TasMod;

public static class PipeHub
{
    private static NamedPipeServerStream? _pipe;
    private static StreamWriter? _writer;
    private static StreamReader? _reader;
    private static int _sequence;
    private static readonly object Gate = new();

    public static void Start(string pipeName)
    {
        var thread = new Thread(() => Serve(pipeName)) { IsBackground = true, Name = "sts2-tas-pipe" };
        thread.Start();
    }

    public static void StartHeartbeat()
    {
        if (Engine.GetMainLoop() is not SceneTree tree)
        {
            return;
        }
        var ticks = 0;
        tree.ProcessFrame += () =>
        {
            ticks += 1;
            if (ticks % 20 == 0)
            {
                Publish();
            }
        };
    }

    public static void Publish()
    {
        MainThread.Run(() =>
        {
            try
            {
                WriteSnapshot();
            }
            catch (Exception ex)
            {
                GD.PrintErr($"Sts2TasMod publish failed: {ex.Message}");
            }
        });
    }

    private static void Serve(string pipeName)
    {
        while (true)
        {
            try
            {
                _pipe = new NamedPipeServerStream(pipeName, PipeDirection.InOut, 1, PipeTransmissionMode.Byte, PipeOptions.Asynchronous);
                _pipe.WaitForConnection();
                var utf8 = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
                _reader = new StreamReader(_pipe, utf8, detectEncodingFromByteOrderMarks: false, bufferSize: 1024, leaveOpen: true);
                _writer = new StreamWriter(_pipe, utf8, bufferSize: 1024, leaveOpen: true) { AutoFlush = true };
                Publish();
                string? line;
                while ((line = _reader.ReadLine()) != null)
                {
                    var captured = line;
                    MainThread.Run(() => CommandRunner.Apply(captured));
                }
            }
            catch (Exception ex)
            {
                GD.PrintErr($"Sts2TasMod pipe loop: {ex.Message}");
            }
            finally
            {
                _writer?.Dispose();
                _reader?.Dispose();
                _pipe?.Dispose();
                _writer = null;
                _reader = null;
                _pipe = null;
            }
        }
    }

    internal static void WriteSnapshot()
    {
        if (_writer is null)
        {
            return;
        }
        lock (Gate)
        {
            _sequence += 1;
            var payload = SnapshotFactory.Capture();
            var frame = JsonSerializer.Serialize(new Dictionary<string, object?>
            {
                ["sequence"] = _sequence,
                ["payload"] = payload
            });
            _writer.WriteLine(frame);
        }
    }
}
