using System.Collections;
using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.MainMenu;
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
        if (IsLoading())
        {
            return Overlay("menu", act, floor, false, Array.Empty<object>(), Array.Empty<object>(), [], loading: true);
        }
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
            ClaimRewards();
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
        List<Dictionary<string, object?>> actions,
        bool loading = false
    )
    {
        if (loading)
        {
            actions = [];
            phase = "menu";
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
                ["loading"] = loading
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

    private static bool _embarked;
    private static string _lastClickId = "";
    private static long _lastClickMs;

    private static void ClickMenu(int slot)
    {
        _ = slot;
        if (_embarked)
        {
            if (NMapScreen.Instance is { IsOpen: true })
            {
                _embarked = false;
            }
            else
            {
                GD.Print("Sts2TasMod waiting after embark");
                return;
            }
        }
        var root = (Engine.GetMainLoop() as SceneTree)?.Root;
        if (DeclineTutorials(root)) { return; }
        if (ClickFirstVisible("NDisclaimerProceedButton")) { return; }
        if (ClickFirstVisible("NFtueConfirmButton")) { return; }
        if (ClickContinue()) { return; }
        if (ClickSingleplayer()) { return; }
        if (ClickStandard()) { return; }
        if (ClickCharacterSelect(root)) { return; }
        ClickNamed(root, "NoButton");
    }

    private static bool IsLoading()
    {
        var root = (Engine.GetMainLoop() as SceneTree)?.Root;
        if (CombatManager.Instance.IsInProgress)
        {
            return false;
        }
        if (NMapScreen.Instance is { IsOpen: true })
        {
            return false;
        }
        if (FindType(root, "NCharacterSelectScreen") is Node character && IsShown(character))
        {
            return false;
        }
        if (NGame.Instance?.MainMenu is CanvasItem menu && menu.IsVisibleInTree())
        {
            return false;
        }
        if (FindType(root, "NSingleplayerSubmenu") is Node submenu && IsShown(submenu))
        {
            return false;
        }
        if (FindType(root, "NAcceptTutorialsFtue") is not null)
        {
            return false;
        }
        if (FindType(root, "NRewardsScreen") is Node rewards && IsShown(rewards))
        {
            return false;
        }
        if (FindType(root, "NCardRewardSelectionScreen") is Node cards && IsShown(cards))
        {
            return false;
        }
        return true;
    }

    private static void ClaimRewards()
    {
        var root = (Engine.GetMainLoop() as SceneTree)?.Root;
        var cardScreen = FindType(root, "NCardRewardSelectionScreen");
        if (cardScreen is not null && IsShown(cardScreen))
        {
            if (PickFirstRewardCard(cardScreen)) { return; }
            if (SkipRewardCards(cardScreen)) { return; }
            return;
        }
        if (ClickFirstVisible("NRewardButton")) { return; }
        ClickFirstVisible("NProceedButton");
    }

    private static bool PickFirstRewardCard(Node screen)
    {
        var row = screen.GetNodeOrNull<Control>("UI/CardRow");
        if (row is not null)
        {
            foreach (var child in row.GetChildren())
            {
                if (child is NCardHolder holder && holder.CardModel is not null && IsShown(holder))
                {
                    holder.EmitSignal(NCardHolder.SignalName.Pressed, holder);
                    GD.Print($"Sts2TasMod selected reward {holder.CardModel.Id.Entry}");
                    return true;
                }
            }
        }
        return false;
    }

    private static bool SkipRewardCards(Node screen)
    {
        var alts = screen.GetNodeOrNull<Control>("UI/RewardAlternatives");
        if (alts is not null)
        {
            foreach (var child in alts.GetChildren())
            {
                if (ClickControl(child))
                {
                    return true;
                }
            }
        }
        return ClickFirstVisible("NChoiceSelectionSkipButton");
    }

    private static bool ClickContinue()
    {
        var menu = NGame.Instance?.MainMenu;
        var button = menu?.GetNodeOrNull<NMainMenuContinueButton>("MainMenuTextButtons/ContinueButton");
        return ClickControl(button) || ClickFirstVisible("NMainMenuContinueButton");
    }

    private static bool ClickSingleplayer()
    {
        var button = NGame.Instance?.MainMenu?.GetNodeOrNull<NMainMenuTextButton>("MainMenuTextButtons/SingleplayerButton");
        return ClickControl(button);
    }

    private static bool ClickStandard()
    {
        var submenu = FindType((Engine.GetMainLoop() as SceneTree)?.Root, "NSingleplayerSubmenu");
        if (submenu is null || !IsShown(submenu))
        {
            return false;
        }
        return ClickControl(submenu.GetNodeOrNull<Node>("StandardButton"))
            || ClickNamed(submenu, "StandardButton")
            || ClickNamed(submenu, "Standard");
    }

    private static int _characterSelectClicks;

    private static bool ClickCharacterSelect(Node? root)
    {
        var screen = FindType(root, "NCharacterSelectScreen");
        if (screen is null || !IsShown(screen))
        {
            _characterSelectClicks = 0;
            return false;
        }
        if (_characterSelectClicks == 0)
        {
            if (ClickFirstVisible("NCharacterSelectButton"))
            {
                _characterSelectClicks = 1;
                return true;
            }
        }
        var embark = screen.GetNodeOrNull<Node>("ConfirmButton");
        if (embark is not null && Enabled(embark) && ClickControl(embark))
        {
            _embarked = true;
            return true;
        }
        _characterSelectClicks = 0;
        return ClickFirstVisible("NCharacterSelectButton");
    }

    private static bool Enabled(Node node)
    {
        var property = node.GetType().GetProperty("IsEnabled");
        return property?.GetValue(node) is not false;
    }

    private static bool DeclineTutorials(Node? root)
    {
        var node = FindType(root, "NAcceptTutorialsFtue");
        if (node is null)
        {
            return false;
        }
        node.Call("NoTutorials");
        return true;
    }

    private static bool IsShown(Node? node)
    {
        return node is CanvasItem canvas && canvas.IsVisibleInTree();
    }

    private static bool ClickNamed(Node? root, string name)
    {
        return ClickControl(FindName(root, name));
    }

    private static bool ClickFirstVisible(string typeName)
    {
        return ClickControl(FindType((Engine.GetMainLoop() as SceneTree)?.Root, typeName));
    }

    private static bool ClickControl(Node? node)
    {
        if (node is null || !IsShown(node))
        {
            return false;
        }
        var id = $"{node.GetType().Name}:{node.Name}";
        var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        if (id == _lastClickId && now - _lastClickMs < 2000)
        {
            return false;
        }
        if (node is NClickableControl clickable)
        {
            clickable.ForceClick();
            _lastClickId = id;
            _lastClickMs = now;
            GD.Print($"Sts2TasMod clicked {id}");
            return true;
        }
        var force = node.GetType().GetMethod("ForceClick");
        if (force is not null)
        {
            force.Invoke(node, null);
            GD.Print($"Sts2TasMod ForceClick {node.Name}");
            return true;
        }
        if (node.HasSignal("Released"))
        {
            node.EmitSignal(NClickableControl.SignalName.Released, node);
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
