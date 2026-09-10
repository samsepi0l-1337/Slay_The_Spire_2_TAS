using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Modding;

namespace Sts2TasMod;

[ModInitializer("Initialize")]
public static class ModEntry
{
    public const string PipeName = "sts2-tas";
    public const string HarmonyId = "sts2-tas.bridge";
    public const string ModVersion = "0.1.0";

    public static void Initialize()
    {
        try
        {
            PatchPoints.AssertPresent();
            var harmony = new Harmony(HarmonyId);
            harmony.PatchAll(Assembly.GetExecutingAssembly());
            PipeHub.Start(PipeName);
            GD.Print($"Sts2TasMod {ModVersion} attached on pipe '{PipeName}'");
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod failed closed: {ex.Message}");
            throw;
        }
    }
}
