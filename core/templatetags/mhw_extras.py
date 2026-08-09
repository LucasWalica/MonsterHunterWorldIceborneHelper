from django import template
from django.utils.html import conditional_escape, format_html

register = template.Library()

ELEMENT_BADGE_CLASSES = {
    "fire": "border-red-500/40 bg-red-500/10 text-red-400",
    "water": "border-blue-500/40 bg-blue-500/10 text-blue-400",
    "thunder": "border-yellow-500/40 bg-yellow-500/10 text-yellow-400",
    "ice": "border-cyan-500/40 bg-cyan-500/10 text-cyan-400",
    "dragon": "border-purple-500/40 bg-purple-500/10 text-purple-400",
    "poison": "border-green-500/40 bg-green-500/10 text-green-400",
    "paralysis": "border-amber-400/40 bg-amber-400/10 text-amber-300",
    "sleep": "border-indigo-500/40 bg-indigo-500/10 text-indigo-400",
    "blast": "border-orange-500/40 bg-orange-500/10 text-orange-400",
    "stun": "border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-400",
}

SHARPNESS_COLORS = {
    "red": "bg-red-600",
    "orange": "bg-orange-500",
    "yellow": "bg-yellow-400",
    "green": "bg-green-500",
    "blue": "bg-blue-500",
    "white": "bg-slate-100",
    "purple": "bg-purple-500",
}

# Orden visual del afilado (de peor a mejor).
SHARPNESS_ORDER = ("red", "orange", "yellow", "green", "blue", "white", "purple")


@register.filter
def element_badge(element):
    """Devuelve un badge HTML con el color del elemento/estado."""
    element = conditional_escape(element)
    classes = ELEMENT_BADGE_CLASSES.get(
        element, "border-slate-500/40 bg-slate-500/10 text-slate-300"
    )
    return format_html(
        '<span class="inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-semibold {}">{}</span>',
        classes,
        element,
    )


@register.filter
def sharpness_segments(sharpness):
    """Convierte el dict de afilado en [(clase_color, %), ...]."""
    if not isinstance(sharpness, dict):
        return []
    total = sum(v for v in sharpness.values() if v)
    if not total:
        return []
    return [
        (SHARPNESS_COLORS.get(color, "bg-slate-500"), round(value / total * 100, 1))
        for color, value in sharpness.items()
        if value
    ]


@register.filter
def sharpness_label(sharpness):
    """Devuelve el color más alto disponible (ej. white/purple) o None."""
    if not isinstance(sharpness, dict):
        return None
    for color in reversed(SHARPNESS_ORDER):
        if sharpness.get(color):
            return color
    return None


@register.filter
def rarity_stars(rarity):
    return "★" * rarity


@register.filter
def socket_spans(slots):
    """Lista de rangos -> spans de ranuras para joyas."""
    if not slots:
        return ""
    colors = {1: "bg-slate-300 text-slate-900", 2: "bg-amber-300 text-slate-900", 3: "bg-sky-400 text-slate-900"}
    return format_html(
        "".join(
            format_html(
                '<span class="inline-flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold {}">{}</span>',
                colors.get(int(rank), "bg-slate-300 text-slate-900"),
                rank,
            )
            for rank in sorted(slots, reverse=True)
        )
    )


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def level_range(max_level):
    """Genera 0..max_level para selects de nivel de habilidad."""
    try:
        return range(int(max_level) + 1)
    except (TypeError, ValueError):
        return range(1)


@register.filter
def stars_html(stars):
    """Estrellas de debilidad rellenas y vacías."""
    stars = int(stars)
    full = "★" * max(stars, 0)
    empty = "☆" * max(3 - stars, 0)
    return conditional_escape(full + empty)
