"""styles — reusable CTK widget style presets built from colors and fonts."""

from theme import colors as C, fonts as F


def card_frame(parent, **kw):
    """Standard card frame kwargs."""
    import customtkinter as ctk
    return ctk.CTkFrame(parent, corner_radius=10, fg_color=C.BG_CARD, **kw)


def section_label(parent, text, **kw):
    """Section heading inside a card or scrollable frame."""
    import customtkinter as ctk
    return ctk.CTkLabel(parent, text=text, font=F.SUBHEADING,
                        text_color=C.TEXT_PRIMARY, **kw)


def muted_label(parent, text, **kw):
    """Small muted label."""
    import customtkinter as ctk
    return ctk.CTkLabel(parent, text=text, font=F.TINY,
                        text_color=C.TEXT_MUTED, **kw)


def primary_button(parent, text, command, **kw):
    """Blue primary action button."""
    import customtkinter as ctk
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=C.ACCENT_BLUE, hover_color=C.ACCENT_BLUE_HOVER,
        font=F.BODY_BOLD, height=34, **kw,
    )


def danger_button(parent, text, command, **kw):
    """Red destructive action button."""
    import customtkinter as ctk
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=C.RED, hover_color=C.RED_DARK,
        font=F.BODY_BOLD, height=28, **kw,
    )


def success_button(parent, text, command, **kw):
    """Green action button."""
    import customtkinter as ctk
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=C.GREEN_DARK, hover_color=C.GREEN_HOVER,
        font=F.BODY_BOLD, height=34, **kw,
    )


def subtle_button(parent, text, command, **kw):
    """Gray subtle button."""
    import customtkinter as ctk
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color="#374151", hover_color="#4b5563",
        font=F.SMALL, height=28, **kw,
    )


def text_entry(parent, variable, width=200, show="", **kw):
    """Styled text entry."""
    import customtkinter as ctk
    return ctk.CTkEntry(
        parent, textvariable=variable, width=width,
        fg_color=C.BG_INPUT, text_color=C.TEXT_SECONDARY,
        border_color=C.BORDER_INPUT, height=32, show=show, **kw,
    )


def dropdown(parent, variable, values, width=200, **kw):
    """Styled dropdown menu."""
    import customtkinter as ctk
    return ctk.CTkOptionMenu(
        parent, values=values, variable=variable, width=width,
        fg_color=C.BG_INPUT, button_color=C.BORDER_INPUT,
        dropdown_fg_color=C.BG_SECONDARY, text_color=C.TEXT_SECONDARY, **kw,
    )


def switch(parent, variable, **kw):
    """Styled toggle switch."""
    import customtkinter as ctk
    return ctk.CTkSwitch(
        parent, text="", variable=variable,
        progress_color=C.ACCENT_BLUE, **kw,
    )


def scrollable_frame(parent, **kw):
    """Dark scrollable frame."""
    import customtkinter as ctk
    return ctk.CTkScrollableFrame(
        parent, fg_color=C.BG_SECONDARY,
        scrollbar_button_color=C.BG_CARD,
        scrollbar_button_hover_color=C.BORDER_INPUT, **kw,
    )
