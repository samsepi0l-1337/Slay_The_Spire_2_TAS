using System.Collections;
using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2TasMod;

public static class RunFlow
{
    public static Dictionary<string, object?> OutOfCombat()
    {
        var run = RunManager.Instance.DebugOnlyGetState();
        var act = (SnapshotFactory.ReadIntPublic(run, "CurrentActIndex") ?? 0) + 1;
        var floor = SnapshotFactory.ReadIntPublic(run, "ActFloor", "TotalFloor") ?? 0;
        var architect = IsArchitect(run);
        var map = MapActions();
        if (map.Count > 0)
        {
            return Overlay("map", act, floor, architect, map, Array.Empty<object>(), map);
        }
        var rewards = RewardActions();
        if (rewards.Count > 0)
        {
            return Overlay("card_reward", act, floor, architect, Array.Empty<object>(), rewards, rewards);
        }
        var events = architect ? [] : MenuActions();
        var phase = architect ? "terminal" : "event";
        return Overlay(phase, act, floor, architect, Array.Empty<object>(), Array.Empty<object>(), events);
    }

    public static void Apply(string actionType, int? slot)
    {
        if (actionType == "choose_map_node")
        {
            ChooseMap(slot ?? 0);
            return;
        }
        if (actionType == "choose_reward")
        {
            ClickFirst("NCardRewardSelectionScreen");
            return;
        }
        ClickMenu(slot ?? 0);
    }

    internal static bool IsArchitect(object? run)
    {
        if (run is null)
        {
            return false;
        }
        foreach (var name in new[] { "CurrentMapPoint", "MapLocation", "CurrentRoom" })
        {
            var value = run.GetType().GetProperty(name)?.GetValue(run)?.ToString() ?? "";
            if (value.Contains("Architect", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }
        return Engine.GetMainLoop() is SceneTree tree && FindType(tree.Root, "NArchitectVfx") is not null;
    }

    private static Dictionary<string, object?> Overlay(
        string phase,
        int act,
        int floor,
        bool architect,
        object mapChoices,
        object rewardChoices,
        List<Dictionary<string, object?>> actions
    )
    {
        return new Dictionary<string, object?>
        {
            ["game_version"] = "v0.107.1",
            ["mod_version"] = ModEntry.ModVersion,
            ["schema_version"] = 1,
            ["seed"] = "live",
            ["timestamp"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
            ["phase"] = architect ? "terminal" : phase,
            ["floor"] = floor,
            ["act"] = act,
            ["screen_id"] = architect ? "architect" : phase,
            ["player"] = new Dictionary<string, object?>
            {
                ["hp"] = 1, ["max_hp"] = 1, ["energy"] = 0, ["block"] = 0, ["gold"] = 0,
                ["powers"] = Array.Empty<object>(), ["resources"] = new Dictionary<string, object?>()
            },
            ["hand"] = Array.Empty<object>(),
            ["draw_pile"] = Array.Empty<object>(),
            ["discard_pile"] = Array.Empty<object>(),
            ["exhaust_pile"] = Array.Empty<object>(),
            ["enemies"] = Array.Empty<object>(),
            ["relics"] = Array.Empty<object>(),
            ["potions"] = Array.Empty<object>(),
            ["map_choices"] = mapChoices,
            ["reward_choices"] = rewardChoices,
            ["shop_choices"] = Array.Empty<object>(),
            ["event_choices"] = actions,
            ["rest_choices"] = Array.Empty<object>(),
            ["valid_actions"] = actions,
            ["extras"] = new Dictionary<string, object?>
            {
                ["game_version"] = "v0.107.1",
                ["architect"] = architect,
                ["reached_act3"] = act >= 3
            }
        };
    }

    private static List<Dictionary<string, object?>> MapActions()
    {
        var coords = TravelableCoords();
        var actions = new List<Dictionary<string, object?>>();
        for (var slot = 0; slot < coords.Count; slot++)
        {
            actions.Add(new Dictionary<string, object?>
            {
                ["action_type"] = "choose_map_node",
                ["args"] = new Dictionary<string, int> { ["node_slot"] = slot }
            });
        }
        return actions;
    }

    private static List<Dictionary<string, object?>> RewardActions()
    {
        if (FindType((Engine.GetMainLoop() as SceneTree)?.Root, "NCardRewardSelectionScreen") is null
            && FindType((Engine.GetMainLoop() as SceneTree)?.Root, "NRewardsScreen") is null)
        {
            return [];
        }
        return
        [
            new Dictionary<string, object?>
            {
                ["action_type"] = "choose_reward",
                ["args"] = new Dictionary<string, int> { ["choice_slot"] = 0 }
            }
        ];
    }

    private static List<Dictionary<string, object?>> MenuActions()
    {
        return
        [
            new Dictionary<string, object?>
            {
                ["action_type"] = "choose_event_option",
                ["args"] = new Dictionary<string, int> { ["choice_slot"] = 0 }
            }
        ];
    }

    private static void ChooseMap(int slot)
    {
        var coords = TravelableCoords();
        if (NMapScreen.Instance is null || coords.Count == 0 || slot < 0 || slot >= coords.Count)
        {
            throw new InvalidOperationException("no travelable map node");
        }
        _ = NMapScreen.Instance.TravelToMapCoord(coords[slot]);
    }

    private static List<MapCoord> TravelableCoords()
    {
        var result = new List<MapCoord>();
        if (NMapScreen.Instance is not { IsOpen: true } map)
        {
            return result;
        }
        var field = map.GetType().GetField("_mapPointDictionary", BindingFlags.Instance | BindingFlags.NonPublic);
        if (field?.GetValue(map) is not IDictionary dict)
        {
            return result;
        }
        foreach (DictionaryEntry entry in dict)
        {
            var state = entry.Value?.GetType().GetProperty("State")?.GetValue(entry.Value)?.ToString();
            if (state == "Travelable" && entry.Key is MapCoord coord)
            {
                result.Add(coord);
            }
        }
        return result;
    }

    private static void ClickMenu(int slot)
    {
        _ = slot;
        var root = (Engine.GetMainLoop() as SceneTree)?.Root;
        if (ClickNamed(root, "ConfirmButton")) { return; }
        if (ClickNamed(root, "SingleplayerButton")) { return; }
        if (ClickNamed(root, "StandardButton")) { return; }
        if (ClickFirst("NCharacterSelectButton")) { return; }
        if (ClickFirst("NReturnToMainMenuButton")) { return; }
        ClickFirst("NDisclaimerProceedButton");
    }

    private static bool ClickNamed(Node? root, string name)
    {
        var node = FindName(root, name);
        return node is not null && Click(node);
    }

    private static bool ClickFirst(string typeName)
    {
        var node = FindType((Engine.GetMainLoop() as SceneTree)?.Root, typeName);
        return node is not null && Click(node);
    }

    private static bool Click(Node node)
    {
        var force = node.GetType().GetMethod("ForceClick");
        if (force is not null)
        {
            force.Invoke(node, null);
            return true;
        }
        if (node.HasSignal("Released"))
        {
            node.EmitSignal("Released", node);
            return true;
        }
        return false;
    }

    private static Node? FindType(Node? node, string typeName)
    {
        if (node is null)
        {
            return null;
        }
        if (node.GetType().Name == typeName)
        {
            return node;
        }
        foreach (var child in node.GetChildren())
        {
            var match = FindType(child, typeName);
            if (match is not null)
            {
                return match;
            }
        }
        return null;
    }

    private static Node? FindName(Node? node, string name)
    {
        if (node is null)
        {
            return null;
        }
        if (node.Name == name)
        {
            return node;
        }
        foreach (var child in node.GetChildren())
        {
            var match = FindName(child, name);
            if (match is not null)
            {
                return match;
            }
        }
        return null;
    }
}
