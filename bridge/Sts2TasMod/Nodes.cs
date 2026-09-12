using Godot;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;

namespace Sts2TasMod;

internal static class Nodes
{
    private static string _lastClickId = "";
    private static long _lastClickMs;

    internal static bool IsShown(Node? node)
    {
        return node is CanvasItem canvas && canvas.IsVisibleInTree();
    }

    internal static bool Enabled(Node node)
    {
        var property = node.GetType().GetProperty("IsEnabled");
        return property?.GetValue(node) is not false;
    }

    internal static bool ClickNamed(Node? root, string name)
    {
        return ClickControl(FindName(root, name));
    }

    internal static bool ClickFirstVisible(string typeName)
    {
        foreach (var node in FindAll((Engine.GetMainLoop() as SceneTree)?.Root, typeName))
        {
            if (ClickControl(node))
            {
                return true;
            }
        }
        return false;
    }

    internal static bool ClickFirstShown(string typeName)
    {
        foreach (var node in FindAll((Engine.GetMainLoop() as SceneTree)?.Root, typeName))
        {
            if (ForceClickRaw(node))
            {
                return true;
            }
        }
        return false;
    }

    internal static bool ForceClickRaw(Node? node)
    {
        if (node is null || !IsShown(node))
        {
            return false;
        }
        var id = $"{node.GetType().Name}:{node.Name}";
        var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        if (id == _lastClickId && now - _lastClickMs < 1500)
        {
            return false;
        }
        if (node is NClickableControl clickable)
        {
            clickable.ForceClick();
            _lastClickId = id;
            _lastClickMs = now;
            GD.Print($"Sts2TasMod raw-click {id}");
            return true;
        }
        var force = node.GetType().GetMethod("ForceClick");
        if (force is not null)
        {
            force.Invoke(node, null);
            _lastClickId = id;
            _lastClickMs = now;
            GD.Print($"Sts2TasMod raw-ForceClick {id}");
            return true;
        }
        return false;
    }

    internal static bool ClickControl(Node? node)
    {
        if (node is null || !IsShown(node) || !Enabled(node))
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
            _lastClickId = id;
            _lastClickMs = now;
            GD.Print($"Sts2TasMod ForceClick {node.Name}");
            return true;
        }
        if (node.HasSignal("Released"))
        {
            node.EmitSignal(NClickableControl.SignalName.Released, node);
            _lastClickId = id;
            _lastClickMs = now;
            GD.Print($"Sts2TasMod released {id}");
            return true;
        }
        if (node.HasSignal("Pressed"))
        {
            node.EmitSignal("Pressed", node);
            _lastClickId = id;
            _lastClickMs = now;
            GD.Print($"Sts2TasMod pressed {id}");
            return true;
        }
        return false;
    }

    internal static IEnumerable<Node> FindAll(Node? node, string typeName)
    {
        if (node is null)
        {
            yield break;
        }
        if (node.GetType().Name == typeName)
        {
            yield return node;
        }
        foreach (var child in node.GetChildren())
        {
            foreach (var match in FindAll(child, typeName))
            {
                yield return match;
            }
        }
    }

    internal static Node? FindType(Node? node, string typeName)
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

    internal static Node? FindName(Node? node, string name)
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

    internal static Node? Root()
    {
        return (Engine.GetMainLoop() as SceneTree)?.Root;
    }
}
