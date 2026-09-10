using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;

namespace Sts2TelemetryBridge;

public static class Program
{
    public static int Main(string[] args)
    {
        var command = args.Length == 0 ? "bridge-smoke" : args[0];
        return command switch
        {
            "bridge-smoke" => BridgeSmoke(),
            "pipe-serve" => PipeServe(args),
            _ => Unknown(command)
        };
    }

    private static int BridgeSmoke()
    {
        var payload = new
        {
            schema_version = 1,
            transport = "fixture",
            fail_closed = true,
            frame = "TelemetrySnapshot"
        };
        Console.WriteLine(JsonSerializer.Serialize(payload));
        return 0;
    }

    private static int Unknown(string command)
    {
        Console.Error.WriteLine($"unsupported command: {command}");
        return 2;
    }

    private static int PipeServe(string[] args)
    {
        var fixture = Arg(args, "--fixture");
        var listen = Arg(args, "--listen") ?? "127.0.0.1:28771";
        if (fixture is null || !File.Exists(fixture))
        {
            Console.Error.WriteLine("pipe-serve requires --fixture PATH");
            return 2;
        }
        var snapshot = File.ReadAllText(fixture);
        using var doc = JsonDocument.Parse(snapshot);
        var parts = listen.Split(':');
        var ip = IPAddress.Parse(parts[0]);
        var port = int.Parse(parts[1]);
        using var listener = new TcpListener(ip, port);
        listener.Start();
        Console.WriteLine(JsonSerializer.Serialize(new { transport = "tcp", listen, fail_closed = true }));
        using var client = listener.AcceptTcpClient();
        using var stream = client.GetStream();
        var utf8 = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
        using var reader = new StreamReader(stream, utf8, leaveOpen: true);
        using var writer = new StreamWriter(stream, utf8, leaveOpen: true) { AutoFlush = true };
        var sequence = 1;
        WriteFrame(writer, sequence, doc.RootElement);
        while (reader.ReadLine() is not null)
        {
            sequence += 1;
            WriteFrame(writer, sequence, doc.RootElement);
        }
        return 0;
    }

    private static void WriteFrame(StreamWriter writer, int sequence, JsonElement payload)
    {
        using var stream = new MemoryStream();
        using (var jsonWriter = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = false }))
        {
            jsonWriter.WriteStartObject();
            jsonWriter.WriteNumber("sequence", sequence);
            jsonWriter.WritePropertyName("payload");
            payload.WriteTo(jsonWriter);
            jsonWriter.WriteEndObject();
        }
        writer.WriteLine(Encoding.UTF8.GetString(stream.ToArray()));
    }

    private static string? Arg(string[] args, string name)
    {
        var index = Array.IndexOf(args, name);
        if (index < 0 || index + 1 >= args.Length)
        {
            return null;
        }
        return args[index + 1];
    }
}
