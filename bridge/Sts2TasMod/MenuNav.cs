using Godot;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Screens.MainMenu;

namespace Sts2TasMod;

internal static class MenuNav
{
    private static bool _embarked;
    private static long _lastAbandonMs;
    private static int _characterSelectClicks;

    internal static bool OnMenuScreens()
    {
        try
        {
            if (MainMenuVisible())
            {
                return true;
            }
            var root = Nodes.Root();
            if (Nodes.FindType(root, "NCharacterSelectScreen") is Node character && Nodes.IsShown(character))
            {
                return true;
            }
            if (Nodes.FindType(root, "NSingleplayerSubmenu") is Node submenu && Nodes.IsShown(submenu))
            {
                return true;
            }
            if (Nodes.FindType(root, "NAcceptTutorialsFtue") is not null)
            {
                return true;
            }
            if (Nodes.FindType(root, "NAbandonRunConfirmPopup") is Node popup && Nodes.IsShown(popup))
            {
                return true;
            }
            return false;
        }
        catch (Exception)
        {
            return false;
        }
    }

    internal static bool MainMenuVisible()
    {
        try
        {
            return NGame.Instance?.MainMenu is CanvasItem menu && menu.IsVisibleInTree();
        }
        catch (Exception)
        {
            return false;
        }
    }

    internal static void ClickMenu()
    {
        if (_embarked)
        {
            if (NMapScreenOpen())
            {
                _embarked = false;
            }
            else
            {
                GD.Print("Sts2TasMod waiting after embark");
                return;
            }
        }
        var root = Nodes.Root();
        if (DeclineTutorials(root)) { return; }
        if (Nodes.ClickFirstVisible("NDisclaimerProceedButton")) { return; }
        if (Nodes.ClickFirstVisible("NFtueConfirmButton")) { return; }
        if (ConfirmAbandonPopup()) { return; }
        if (AbandonSaveIfPresent()) { return; }
        if (ClickSingleplayer()) { return; }
        if (ClickStandard()) { return; }
        if (ClickCharacterSelect(root)) { return; }
        Nodes.ClickNamed(root, "NoButton");
        GD.Print("Sts2TasMod ClickMenu no-op");
    }

    private static bool NMapScreenOpen()
    {
        try
        {
            return MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen.Instance is { IsOpen: true };
        }
        catch (Exception)
        {
            return false;
        }
    }

    private static bool ConfirmAbandonPopup()
    {
        var popup = Nodes.FindType(Nodes.Root(), "NAbandonRunConfirmPopup");
        if (popup is null || !Nodes.IsShown(popup))
        {
            return false;
        }
        if (Nodes.ClickFirstShown("NConfirmButton")
            || Nodes.ClickNamed(popup, "YesButton")
            || Nodes.ClickNamed(popup, "ConfirmButton")
            || Nodes.ClickNamed(popup, "AbandonButton")
            || Nodes.ClickFirstShown("NPrimaryButton"))
        {
            GD.Print("Sts2TasMod confirm abandon popup");
            return true;
        }
        foreach (var child in popup.GetChildren())
        {
            if (Nodes.ForceClickRaw(child))
            {
                GD.Print("Sts2TasMod confirm abandon child");
                return true;
            }
        }
        return false;
    }

    private static bool AbandonSaveIfPresent()
    {
        var menu = NGame.Instance?.MainMenu;
        var cont = menu?.GetNodeOrNull<NMainMenuContinueButton>("MainMenuTextButtons/ContinueButton");
        if (cont is null || !Nodes.IsShown(cont))
        {
            return false;
        }
        var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        if (now - _lastAbandonMs < 4000)
        {
            return false;
        }
        try
        {
            menu!.AbandonRun();
            _lastAbandonMs = now;
            GD.Print("Sts2TasMod abandon run for Ironclad");
            return true;
        }
        catch (Exception ex)
        {
            GD.PrintErr($"Sts2TasMod abandon failed: {ex.Message}");
            return false;
        }
    }

    private static bool ClickSingleplayer()
    {
        var button = NGame.Instance?.MainMenu?.GetNodeOrNull<NMainMenuTextButton>("MainMenuTextButtons/SingleplayerButton");
        if (Nodes.ForceClickRaw(button) || Nodes.ClickControl(button))
        {
            GD.Print("Sts2TasMod Singleplayer");
            return true;
        }
        return false;
    }

    private static bool ClickStandard()
    {
        var submenu = Nodes.FindType(Nodes.Root(), "NSingleplayerSubmenu");
        if (submenu is null || !Nodes.IsShown(submenu))
        {
            return false;
        }
        if (Nodes.ClickControl(submenu.GetNodeOrNull<Node>("StandardButton"))
            || Nodes.ClickNamed(submenu, "StandardButton")
            || Nodes.ClickNamed(submenu, "Standard")
            || Nodes.ForceClickRaw(submenu.GetNodeOrNull<Node>("StandardButton")))
        {
            GD.Print("Sts2TasMod Standard");
            return true;
        }
        return false;
    }

    private static bool ClickCharacterSelect(Node? root)
    {
        var screen = Nodes.FindType(root, "NCharacterSelectScreen");
        if (screen is null || !Nodes.IsShown(screen))
        {
            _characterSelectClicks = 0;
            return false;
        }
        if (_characterSelectClicks == 0)
        {
            if (Nodes.ClickFirstVisible("NCharacterSelectButton"))
            {
                _characterSelectClicks = 1;
                GD.Print("Sts2TasMod Ironclad");
                return true;
            }
        }
        var embark = screen.GetNodeOrNull<Node>("ConfirmButton");
        if (embark is not null && Nodes.Enabled(embark) && Nodes.ClickControl(embark))
        {
            _embarked = true;
            GD.Print("Sts2TasMod Embark");
            return true;
        }
        _characterSelectClicks = 0;
        return Nodes.ClickFirstVisible("NCharacterSelectButton");
    }

    private static bool DeclineTutorials(Node? root)
    {
        var node = Nodes.FindType(root, "NAcceptTutorialsFtue");
        if (node is null)
        {
            return false;
        }
        node.Call("NoTutorials");
        GD.Print("Sts2TasMod NoTutorials");
        return true;
    }
}
