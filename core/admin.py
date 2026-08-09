from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import (
    Armor,
    ArmorSkill,
    Charm,
    CharmSkill,
    CraftingMaterial,
    Decoration,
    DecorationSkill,
    Hitzone,
    Item,
    Location,
    Monster,
    MonsterAilment,
    MonsterResistance,
    MonsterReward,
    MonsterWeakness,
    Skill,
    SkillRank,
    Weapon,
)


class MonsterWeaknessInline(admin.TabularInline):
    model = MonsterWeakness
    extra = 0


class MonsterResistanceInline(admin.TabularInline):
    model = MonsterResistance
    extra = 0


class MonsterAilmentInline(admin.TabularInline):
    model = MonsterAilment
    extra = 0


class HitzoneInline(admin.TabularInline):
    model = Hitzone
    extra = 0


@admin.register(Monster)
class MonsterAdmin(admin.ModelAdmin):
    list_display = ("game_id", "name", "type", "species")
    list_filter = ("type", "species")
    search_fields = ("name", "species")
    inlines = [
        MonsterWeaknessInline,
        MonsterResistanceInline,
        MonsterAilmentInline,
        HitzoneInline,
    ]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("game_id", "name", "zone_count")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("game_id", "name", "rarity", "value")
    list_filter = ("rarity",)
    search_fields = ("name",)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("game_id", "name", "max_level")
    search_fields = ("name",)


@admin.register(SkillRank)
class SkillRankAdmin(admin.ModelAdmin):
    list_display = ("skill", "level")
    list_filter = ("level",)


class ArmorSkillInline(admin.TabularInline):
    model = ArmorSkill
    extra = 0


class ArmorMaterialInline(GenericTabularInline):
    model = CraftingMaterial
    extra = 0
    fields = ("item", "quantity", "kind")


@admin.register(Armor)
class ArmorAdmin(admin.ModelAdmin):
    list_display = ("game_id", "name", "type", "rank", "rarity", "defense_base")
    list_filter = ("type", "rank", "rarity")
    search_fields = ("name",)
    inlines = [ArmorSkillInline, ArmorMaterialInline]


class WeaponMaterialInline(GenericTabularInline):
    model = CraftingMaterial
    extra = 0
    fields = ("item", "quantity", "kind")


@admin.register(Weapon)
class WeaponAdmin(admin.ModelAdmin):
    list_display = (
        "game_id",
        "name",
        "weapon_type",
        "rarity",
        "attack_raw",
        "affinity",
    )
    list_filter = ("weapon_type", "rarity")
    search_fields = ("name",)
    inlines = [WeaponMaterialInline]


@admin.register(MonsterReward)
class MonsterRewardAdmin(admin.ModelAdmin):
    list_display = ("monster", "item")
    list_filter = ("monster",)


@admin.register(CraftingMaterial)
class CraftingMaterialAdmin(admin.ModelAdmin):
    list_display = ("item", "quantity", "kind", "content_type")
    search_fields = ("item__name",)


class DecorationSkillInline(admin.TabularInline):
    model = DecorationSkill
    extra = 0


@admin.register(Decoration)
class DecorationAdmin(admin.ModelAdmin):
    list_display = ("game_id", "name", "rarity", "slot")
    list_filter = ("slot", "rarity")
    search_fields = ("name",)
    inlines = [DecorationSkillInline]


class CharmSkillInline(admin.TabularInline):
    model = CharmSkill
    extra = 0


class CharmMaterialInline(GenericTabularInline):
    model = CraftingMaterial
    extra = 0
    fields = ("item", "quantity", "kind")


@admin.register(Charm)
class CharmAdmin(admin.ModelAdmin):
    list_display = ("game_id", "name", "rarity", "crafting_cost")
    list_filter = ("rarity",)
    search_fields = ("name",)
    inlines = [CharmSkillInline, CharmMaterialInline]
