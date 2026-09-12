using System.Collections;
using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2TasMod;

public static class RunFlow
{
    public static Dictionary<string, object?> OutOfCombat()
    {
        try
        {
            var run = RunManager.Instance?.DebugOnlyGetState();
            var act = (SnapshotFactory.ReadIntPublic(run, "CurrentActIndex") ?? 0) + 1;
            var floor = SnapshotFactory.ReadIntPublic(run, "ActFloor", "TotalFloor") ?? 0;
            var architect = IsArchitect(run);
            if (IsLoading())
            {
                return Overlay("menu", act, floor, architect, Array.Empty<object>(), Array.Empty<object>(), [], "loading", true);
            }
            var map = MapActions();
            if (map.Count > 0)
            {
                return Overlay("map", act, floor, architect, map, Array.Empty<object>(), map, "map");
            }
            var rewards = EventReward.RewardActions();
            if (rewards.Count > 0)
            {
                return Overlay("card_reward", act, floor, architect, Array.Empty<object>(), rewards, rewards, "rewards");
            }
            var eventActions = EventReward.EventActions();
            if (eventActions.Count > 0)
            {
                return Overlay("event", act, floor, architect, Array.Empty<object>(), Array.Empty<object>(), eventActions, "event");
            }
            var ui = DetectUi();
            var events = architect ? [] : MenuActions();
            var phase = architect ? "terminal" : "event";
            return Overlay(phase, act, floor, architect, Array.Empty<object>(), Array.Empty<object>(), events, ui);
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod OutOfCombat failed: {ex}");
            return Overlay("menu", 1, 0, false, Array.Empty<object>(), Array.Empty<object>(), [], "loading", true);
        }
    }

    public static void Apply(string actionType, int? slot)
    {
        GD.Print($"Sts2TasMod apply {actionType} slot={slot} ui={DetectUi()}");
        if (MenuNav.OnMenuScreens())
        {
            MenuNav.ClickMenu();
            return;
        }
        if (actionType == "choose_map_node")
        {
            ChooseMap(slot ?? 0);
            return;
        }
        if (actionType == "choose_reward")
        {
            EventReward.ClaimRewards();
            return;
        }
        if (actionType == "choose_event_option" && InEventRoom())
        {
            EventReward.ChooseEvent(slot ?? 0);
            return;
        }
        if (ScreenAdvance.TryWorld())
        {
            return;
        }
        MenuNav.ClickMenu();
    }

    internal static bool InEventRoom()
    {
        try
        {
            var room = NEventRoom.Instance;
            if (room is null || !room.IsInsideTree())
            {
                return false;
            }
            return room is not CanvasItem canvas || canvas.IsVisibleInTree();
        }
        catch (Exception)
        {
            return false;
        }
    }

    internal static bool IsVictory()
    {
        var root = Nodes.Root();
        foreach (var name in new[] { "NVictoryScreen", "NVictoryOverlay", "NRunCompleteScreen", "NGameWinOverlay", "NCreditsScreen" })
        {
            if (Nodes.FindType(root, name) is Node node && Nodes.IsShown(node))
            {
                return true;
            }
        }
        return false;
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
        return Engine.GetMainLoop() is SceneTree tree && Nodes.FindType(tree.Root, "NArchitectVfx") is not null;
    }

    internal static string DetectUi()
    {
        if (MenuNav.OnMenuScreens()) { return "menu"; }
        if (InEventRoom()) { return "event"; }
        try
        {
            if (NMapScreen.Instance is { IsOpen: true }) { return "map"; }
        }
        catch (Exception) { }
        var root = Nodes.Root();
        if (Nodes.FindType(root, "NRewardsScreen") is Node rewards && Nodes.IsShown(rewards)) { return "rewards"; }
        if (Nodes.FindType(root, "NCardRewardSelectionScreen") is Node cards && Nodes.IsShown(cards)) { return "rewards"; }
        if (ScreenAdvance.InWorldRoom()) { return "world"; }
        if (IsLoading()) { return "loading"; }
        return "unknown";
    }

    private static Dictionary<string, object?> Overlay(
        string phase,
        int act,
        int floor,
        bool architect,
        object mapChoices,
        object rewardChoices,
        List<Dictionary<string, object?>> actions,
        string ui,
        bool loading = false
    )
    {
        if (loading)
        {
            actions = [];
            phase = "menu";
            ui = "loading";
        }
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
            ["screen_id"] = architect ? "architect" : loading ? "loading" : phase,
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
                ["reached_act3"] = act >= 3,
                ["act3_boss_cleared"] = architect || IsVictory(),
                ["victory"] = IsVictory(),
                ["loading"] = loading,
                ["ui"] = ui
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
        GD.Print($"Sts2TasMod map slot={slot}");
    }

    private static List<MapCoord> TravelableCoords()
    {
        var result = new List<MapCoord>();
        NMapScreen? map;
        try
        {
            map = NMapScreen.Instance is { IsOpen: true } open ? open : null;
        }
        catch (Exception)
        {
            return result;
        }
        if (map is null)
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

    private static bool IsLoading()
    {
        var root = Nodes.Root();
        if (CombatManager.Instance is { IsInProgress: true }) { return false; }
        try
        {
            if (NMapScreen.Instance is { IsOpen: true }) { return false; }
        }
        catch (Exception) { }
        if (MenuNav.OnMenuScreens()) { return false; }
        if (Nodes.FindType(root, "NRewardsScreen") is Node rewards && Nodes.IsShown(rewards)) { return false; }
        if (Nodes.FindType(root, "NCardRewardSelectionScreen") is Node cards && Nodes.IsShown(cards)) { return false; }
        if (IsVictory()) { return false; }
        if (InEventRoom()) { return false; }
        if (ScreenAdvance.InWorldRoom()) { return false; }
        return true;
    }
}
