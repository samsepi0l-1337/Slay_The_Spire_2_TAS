using System.Text.Json;

namespace Sts2TelemetryBridge;

public static class Program
{
    public static int Main(string[] args)
    {
        var command = args.Length == 0 ? "bridge-smoke" : args[0];
        if (command != "bridge-smoke")
        {
            Console.Error.WriteLine("Only fixture bridge-smoke is implemented in this skeleton bridge.");
            return 2;
        }

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
}
