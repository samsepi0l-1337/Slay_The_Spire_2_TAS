using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;

namespace Sts2TasMod;

public static class SnapshotFactory
{
    public static Dictionary<string, object?> Capture()
    {
        var combat = CombatManager.Instance;
        if (!combat.IsInProgress)
        {
            return MenuSnapshot("menu");
        }
        var state = combat.DebugOnlyGetState();
        var player = state?.Players.Count > 0 ? state.Players[0] : null;
        if (state is null || player?.PlayerCombatState is null)
        {
            return MenuSnapshot("combat");
        }
        var pcs = player.PlayerCombatState;
        var hand = Cards(pcs.Hand);
        var enemies = Enemies(state);
        var playPhase = ReadBool(combat, "IsPlayPhase") ?? pcs.Phase.ToString().Contains("Play", StringComparison.OrdinalIgnoreCase);
        var actions = LegalActions(pcs.Hand, enemies, playPhase);
        return new Dictionary<string, object?>
        {
            ["game_version"] = "v0.107.1",
            ["mod_version"] = ModEntry.ModVersion,
            ["schema_version"] = 1,
            ["seed"] = "live",
            ["timestamp"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
            ["phase"] = combat.IsOverOrEnding || !player.Creature.IsAlive ? "terminal" : "combat",
            ["floor"] = 1,
            ["act"] = 1,
            ["screen_id"] = playPhase ? "combat-play" : "combat",
            ["player"] = new Dictionary<string, object?>
            {
                ["hp"] = ReadInt(player.Creature, "CurrentHp", "Hp") ?? 0,
                ["max_hp"] = ReadInt(player.Creature, "MaxHp") ?? 0,
                ["energy"] = ReadInt(pcs, "Energy", "CurrentEnergy") ?? 0,
                ["block"] = ReadInt(player.Creature, "Block", "CurrentBlock") ?? 0,
                ["gold"] = ReadInt(player, "Gold") ?? 0,
                ["powers"] = Array.Empty<object>(),
                ["resources"] = new Dictionary<string, object?>()
            },
            ["hand"] = hand,
            ["draw_pile"] = Cards(pcs.DrawPile),
            ["discard_pile"] = Cards(pcs.DiscardPile),
            ["exhaust_pile"] = Cards(pcs.ExhaustPile),
            ["enemies"] = enemies,
            ["relics"] = Array.Empty<object>(),
            ["potions"] = Array.Empty<object>(),
            ["map_choices"] = Array.Empty<object>(),
            ["reward_choices"] = Array.Empty<object>(),
            ["shop_choices"] = Array.Empty<object>(),
            ["event_choices"] = Array.Empty<object>(),
            ["rest_choices"] = Array.Empty<object>(),
            ["valid_actions"] = actions,
            ["extras"] = new Dictionary<string, object?> { ["game_version"] = "v0.107.1" }
        };
    }

    private static Dictionary<string, object?> MenuSnapshot(string phase)
    {
        return new Dictionary<string, object?>
        {
            ["game_version"] = "v0.107.1",
            ["mod_version"] = ModEntry.ModVersion,
            ["schema_version"] = 1,
            ["seed"] = "unknown",
            ["timestamp"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
            ["phase"] = phase == "combat" ? "combat" : "menu",
            ["floor"] = 0,
            ["act"] = 0,
            ["screen_id"] = phase,
            ["player"] = new Dictionary<string, object?>
            {
                ["hp"] = 0, ["max_hp"] = 0, ["energy"] = 0, ["block"] = 0, ["gold"] = 0,
                ["powers"] = Array.Empty<object>(), ["resources"] = new Dictionary<string, object?>()
            },
            ["hand"] = Array.Empty<object>(),
            ["draw_pile"] = Array.Empty<object>(),
            ["discard_pile"] = Array.Empty<object>(),
            ["exhaust_pile"] = Array.Empty<object>(),
            ["enemies"] = Array.Empty<object>(),
            ["relics"] = Array.Empty<object>(),
            ["potions"] = Array.Empty<object>(),
            ["map_choices"] = Array.Empty<object>(),
            ["reward_choices"] = Array.Empty<object>(),
            ["shop_choices"] = Array.Empty<object>(),
            ["event_choices"] = Array.Empty<object>(),
            ["rest_choices"] = Array.Empty<object>(),
            ["valid_actions"] = phase == "combat" ? new object[] { new Dictionary<string, object?> { ["action_type"] = "end_turn", ["args"] = new Dictionary<string, int>() } } : Array.Empty<object>(),
            ["extras"] = new Dictionary<string, object?> { ["game_version"] = "v0.107.1" }
        };
    }

    private static List<Dictionary<string, object?>> Cards(CardPile? pile)
    {
        var cards = new List<Dictionary<string, object?>>();
        if (pile is null)
        {
            return cards;
        }
        foreach (var card in pile.Cards)
        {
            cards.Add(Card(card));
        }
        return cards;
    }

    private static Dictionary<string, object?> Card(CardModel card)
    {
        var targeted = card.TargetType.ToString() == "AnyEnemy";
        var cost = ReadInt(card, "CanonicalEnergyCost") ?? 0;
        return new Dictionary<string, object?>
        {
            ["id"] = card.Id.Entry,
            ["name"] = card.Id.Entry,
            ["cost"] = cost,
            ["type"] = targeted ? "attack" : "skill",
            ["damage"] = targeted ? cost : 0,
            ["block"] = card.GainsBlock ? 1 : 0
        };
    }

    private static List<Dictionary<string, object?>> Enemies(CombatState state)
    {
        var enemies = new List<Dictionary<string, object?>>();
        var index = 0;
        foreach (var creature in state.HittableEnemies)
        {
            enemies.Add(Enemy(creature, index));
            index += 1;
        }
        if (enemies.Count == 0)
        {
            foreach (var creature in state.Enemies)
            {
                enemies.Add(Enemy(creature, index));
                index += 1;
            }
        }
        return enemies;
    }

    private static Dictionary<string, object?> Enemy(Creature creature, int slot)
    {
        return new Dictionary<string, object?>
        {
            ["id"] = creature.Monster?.Id.Entry ?? $"enemy-{slot}",
            ["slot"] = slot,
            ["hp"] = ReadInt(creature, "CurrentHp", "Hp") ?? 0,
            ["block"] = ReadInt(creature, "Block", "CurrentBlock") ?? 0,
            ["intent"] = "unknown",
            ["powers"] = Array.Empty<object>()
        };
    }

    private static List<Dictionary<string, object?>> LegalActions(CardPile hand, List<Dictionary<string, object?>> enemies, bool playPhase)
    {
        var actions = new List<Dictionary<string, object?>>();
        if (!playPhase)
        {
            return actions;
        }
        for (var slot = 0; slot < hand.Cards.Count; slot++)
        {
            var card = hand.Cards[slot];
            if (!card.CanPlay(out _, out _))
            {
                continue;
            }
            if (card.TargetType.ToString() == "AnyEnemy")
            {
                for (var target = 0; target < enemies.Count; target++)
                {
                    if (Convert.ToInt32(enemies[target]["hp"]) <= 0)
                    {
                        continue;
                    }
                    actions.Add(PlayCard(slot, target));
                }
                continue;
            }
            actions.Add(new Dictionary<string, object?>
            {
                ["action_type"] = "play_card",
                ["args"] = new Dictionary<string, int> { ["hand_slot"] = slot }
            });
        }
        actions.Add(new Dictionary<string, object?> { ["action_type"] = "end_turn", ["args"] = new Dictionary<string, int>() });
        return actions;
    }

    private static Dictionary<string, object?> PlayCard(int handSlot, int targetSlot)
    {
        return new Dictionary<string, object?>
        {
            ["action_type"] = "play_card",
            ["args"] = new Dictionary<string, int> { ["hand_slot"] = handSlot, ["target_slot"] = targetSlot }
        };
    }

    private static bool? ReadBool(object? target, params string[] names)
    {
        if (target is null)
        {
            return null;
        }
        foreach (var name in names)
        {
            var property = target.GetType().GetProperty(name);
            if (property?.GetValue(target) is bool flag)
            {
                return flag;
            }
        }
        return null;
    }

    private static int? ReadInt(object? target, params string[] names)
    {
        if (target is null)
        {
            return null;
        }
        foreach (var name in names)
        {
            var property = target.GetType().GetProperty(name);
            if (property is null)
            {
                continue;
            }
            var value = property.GetValue(target);
            if (value is int number)
            {
                return number;
            }
            if (value is IConvertible convertible)
            {
                try
                {
                    return convertible.ToInt32(null);
                }
                catch (Exception)
                {
                    continue;
                }
            }
        }
        return null;
    }
}
