using System.Text.Json;

namespace Sts2Bridge;

public sealed record MacroCommand(string ActionType, IReadOnlyDictionary<string, int> Args)
{
    public static MacroCommand Validate(string line, JsonElement snapshot)
    {
        using var document = JsonDocument.Parse(line);
        var root = document.RootElement;
        RequireObject(root);
        if (!root.TryGetProperty("schema_version", out var schema) || schema.ValueKind != JsonValueKind.Number || !schema.TryGetInt32(out var version) || version != 1)
            throw new InvalidOperationException("unsupported schema_version");
        ReadText(root, "run_id");
        if (ReadText(root, "expected_screen_id") != ReadText(snapshot, "screen_id"))
            throw new InvalidOperationException("expected_screen_id mismatch");
        var action = root.GetProperty("action");
        RequireObject(action);
        var type = ReadText(action, "action_type");
        var required = type switch
        {
            "play_card" => "hand_slot",
            "end_turn" => null,
            "choose_map_node" => "node_slot",
            "choose_reward" or "choose_event_option" => "choice_slot",
            "shop_buy" => "item_slot",
            "shop_remove" => "card_slot",
            _ => throw new InvalidOperationException("unsupported action_type")
        };
        var rawArgs = action.GetProperty("args");
        RequireObject(rawArgs);
        var args = new Dictionary<string, int>();
        foreach (var property in rawArgs.EnumerateObject())
        {
            if (property.Name != required && !(type == "play_card" && property.Name == "target_slot"))
                throw new InvalidOperationException("unexpected action argument");
            if (property.Value.ValueKind != JsonValueKind.Number || !property.Value.TryGetInt32(out var value) || value < 0)
                throw new InvalidOperationException("action argument must be a nonnegative integer");
            args.Add(property.Name, value);
        }
        if (required is not null && !args.ContainsKey(required))
            throw new InvalidOperationException($"missing {required}");
        if (!snapshot.GetProperty("valid_actions").EnumerateArray().Any(candidate => Matches(candidate, type, args)))
            throw new InvalidOperationException("action is not currently legal");
        return new MacroCommand(type, args);
    }

    private static bool Matches(JsonElement candidate, string type, Dictionary<string, int> args)
    {
        if (candidate.GetProperty("action_type").GetString() != type)
            return false;
        var advertised = candidate.GetProperty("args").EnumerateObject().ToArray();
        return advertised.Length == args.Count && advertised.All(property =>
            args.TryGetValue(property.Name, out var value) && property.Value.TryGetInt32(out var expected) && value == expected);
    }

    private static string ReadText(JsonElement root, string name)
    {
        var value = root.GetProperty(name);
        if (value.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(value.GetString()))
            throw new InvalidOperationException($"{name} must be a nonempty string");
        return value.GetString()!;
    }

    private static void RequireObject(JsonElement value)
    {
        if (value.ValueKind != JsonValueKind.Object)
            throw new InvalidOperationException("command fields must be objects");
        var names = new HashSet<string>();
        if (value.EnumerateObject().Any(property => !names.Add(property.Name)))
            throw new InvalidOperationException("duplicate command field");
    }
}
