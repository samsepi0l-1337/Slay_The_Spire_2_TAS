using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;

namespace Sts2TasMod;

[HarmonyPatch(typeof(CombatStateTracker), "NotifyCombatStateChanged")]
public static class CombatStateChangedPatch
{
    public static void Postfix()
    {
        PipeHub.Publish();
    }
}
