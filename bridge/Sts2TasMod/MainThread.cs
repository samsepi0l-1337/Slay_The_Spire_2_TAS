using Godot;

namespace Sts2TasMod;

public static class MainThread
{
    public static void Run(Action action)
    {
        Callable.From(action).CallDeferred();
    }
}
