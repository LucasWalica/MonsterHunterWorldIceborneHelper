"""Tests unitarios de la app core: EFR, optimizador y vistas."""

from django.test import TestCase
from django.urls import reverse

from core.models import (
    Armor,
    ArmorSkill,
    Charm,
    Decoration,
    DecorationSkill,
    Monster,
    Skill,
    Weapon,
)
from core.services.efr import calculate_efr
from core.services.optimizer import SLOT_ORDER, find_sets, total_skills


class WeaponFactory:
    """Construye armas mínimas para la calculadora."""

    @staticmethod
    def make(*, raw=100, affinity=0, elements=None, sharpness=None):
        return Weapon.objects.create(
            game_id=1000 + Weapon.objects.count(),
            name="Arma de prueba",
            weapon_type="great-sword",
            attack_display=raw,
            attack_raw=raw,
            affinity=affinity,
            elements=elements or [],
            sharpness=sharpness
            or {"red": 90, "orange": 60, "yellow": 60, "green": 100,
                "blue": 40, "white": 0, "purple": 0},
        )


class EFRServicesTests(TestCase):
    def test_base_efr_green(self):
        weapon = WeaponFactory.make(raw=100, affinity=0)
        result = calculate_efr(weapon, sharpness="green")
        self.assertAlmostEqual(result.effective_raw, 105.0, places=2)

    def test_sharpness_multipliers(self):
        weapon = WeaponFactory.make(raw=100, affinity=0)
        expected = {"green": 105.0, "blue": 120.0, "white": 132.0}
        for sharpness, value in expected.items():
            result = calculate_efr(weapon, sharpness=sharpness)
            self.assertAlmostEqual(
                result.effective_raw, value, places=2, msg=sharpness
            )

    def test_attack_boost_7(self):
        weapon = WeaponFactory.make(raw=100, affinity=0)
        result = calculate_efr(
            weapon, sharpness="blue", skills={"attack_boost": 7}
        )
        self.assertEqual(result.raw_after_skills, 121)
        # AB7 aporta +5 de afinidad -> factor 1 + 0.05 * 0.25.
        self.assertAlmostEqual(result.effective_raw, 121 * 1.20 * 1.0125, places=2)

    def test_critical_affinity_factor(self):
        weapon = WeaponFactory.make(raw=100, affinity=100)
        result = calculate_efr(weapon, sharpness="green")
        self.assertAlmostEqual(result.effective_raw, 100 * 1.05 * 1.25, places=2)

    def test_affinity_clamped_to_100(self):
        weapon = WeaponFactory.make(raw=100, affinity=90)
        result = calculate_efr(
            weapon, sharpness="green", skills={"critical_eye": 7}
        )
        self.assertEqual(result.affinity, 100)

    def test_elemental_true_value_and_multiplier(self):
        weapon = WeaponFactory.make(raw=100, elements=[{"type": "fire", "damage": 240}])
        result = calculate_efr(weapon, sharpness="green")
        self.assertEqual(result.elements[0]["true_value"], 24.0)
        self.assertAlmostEqual(result.effective_element_total, 24.0, places=2)

    def test_elemental_attack_boost(self):
        weapon = WeaponFactory.make(
            raw=100, elements=[{"type": "fire", "damage": 240}]
        )
        result = calculate_efr(
            weapon, sharpness="green", skills={"elemental_attack": 3}
        )
        self.assertAlmostEqual(result.effective_element_total, 34.0, places=2)

    def test_estimated_hit_uses_hitzone(self):
        weapon = WeaponFactory.make(
            raw=100, elements=[{"type": "fire", "damage": 100}]
        )
        result = calculate_efr(
            weapon,
            sharpness="green",
            sample_hitzone=(60, 30),
            motion_value=1.0,
        )
        self.assertAlmostEqual(result.estimated_raw_hit, 105 * 0.60, places=2)
        self.assertAlmostEqual(result.estimated_element_hit, 10 * 0.30, places=2)


class OptimizerServicesTests(TestCase):
    def setUp(self):
        self.skill = Skill.objects.create(
            game_id=1, name="Attack Boost", max_level=7
        )
        for slot in SLOT_ORDER:
            armor = Armor.objects.create(
                game_id=2000 + len(Armor.objects.all()),
                name=f"Pieza {slot}",
                type=slot,
                rank="master",
                defense_max=100,
            )
            ArmorSkill.objects.create(
                armor=armor, skill=self.skill, level=2
            )

    def test_empty_desired_returns_empty(self):
        self.assertEqual(find_sets({}), [])

    def test_finds_set_with_required_skill(self):
        sets = find_sets({"Attack Boost": 7}, rank="master")
        self.assertEqual(len(sets), 1)
        piece = sets[0][0]
        self.assertTrue(piece.armor_skills.filter(skill=self.skill).exists())

    def test_no_candidates_returns_empty(self):
        sets = find_sets({"Skill Inexistente": 1}, rank="master")
        self.assertEqual(sets, [])

    def test_total_skills_sums_levels(self):
        pieces = list(Armor.objects.filter(rank="master"))
        totals = total_skills(pieces)
        self.assertEqual(totals["Attack Boost"], 2 * len(SLOT_ORDER))


class ViewTests(TestCase):
    def setUp(self):
        self.weapon = WeaponFactory.make(
            raw=190, elements=[{"type": "fire", "damage": 240}]
        )
        self.monster = Monster.objects.create(
            game_id=1, name="Rathalos", type="large", species="Flying Wyvern"
        )

    def test_home_returns_200(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)

    def test_weapon_list_returns_200(self):
        response = self.client.get(reverse("core:weapon_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Arma de prueba")

    def test_weapon_list_element_filter(self):
        response = self.client.get(
            reverse("core:weapon_list"), {"element": "fire"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Arma de prueba")

    def test_calculator_renders_efr(self):
        response = self.client.get(
            reverse("core:efr_calculator"),
            {"weapon": self.weapon.pk, "sharpness": "blue"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EFR Raw")

    def test_weapon_search_returns_matches(self):
        response = self.client.get(
            reverse("core:weapon_search"), {"q": "prueba"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Arma de prueba")
        self.assertContains(response, "Great Sword")

    def test_weapon_search_empty_query_returns_nothing(self):
        response = self.client.get(reverse("core:weapon_search"), {"q": ""})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Arma de prueba")

    def test_weapon_search_no_matches_shows_message(self):
        response = self.client.get(
            reverse("core:weapon_search"), {"q": "zzzzz-no-existe"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No matches")

    def test_decoration_search_returns_matches(self):
        Decoration.objects.create(game_id=500, name="Attack Jewel 1", slot=1)
        response = self.client.get(
            reverse("core:decoration_search"), {"q": "attack"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attack Jewel 1")

    def test_decoration_search_respects_max_slot(self):
        Decoration.objects.create(game_id=501, name="Attack Jewel 2", slot=2)
        response = self.client.get(
            reverse("core:decoration_search"), {"q": "attack", "max_slot": 1}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Attack Jewel 2")

    def test_decoration_search_empty_query_returns_popular(self):
        Decoration.objects.create(game_id=502, name="Attack Jewel 1", slot=1, rarity=7)
        response = self.client.get(
            reverse("core:decoration_search"), {"q": "", "max_slot": 1}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attack Jewel 1")

    def test_set_builder_shows_slot_size_hint(self):
        armor = Armor.objects.create(
            game_id=7000,
            name="Test Helm",
            type="head",
            rank="master",
            slots=[2],
        )
        response = self.client.get(
            reverse("core:set_builder"), {"head": armor.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "deco-pip-head-0")
        self.assertContains(response, "[2]")

    def test_set_builder_renders_one_jewel_pip_per_slot(self):
        armor = Armor.objects.create(
            game_id=7001,
            name="Slotty Helm",
            type="head",
            rank="master",
            slots=[4, 1],
        )
        response = self.client.get(
            reverse("core:set_builder"), {"head": armor.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "deco-pip-head-0")
        self.assertContains(response, "deco-pip-head-1")
        self.assertContains(response, "openJewelModal('head-0', 4)")
        self.assertContains(response, "openJewelModal('head-1', 1)")
        self.assertNotContains(response, "deco-pip-chest")

    def test_set_builder_totals_include_multiple_jewels_per_piece(self):
        armor = Armor.objects.create(
            game_id=7002,
            name="Twin Slot Helm",
            type="head",
            rank="master",
            slots=[1, 1],
        )
        skill_a = Skill.objects.create(game_id=9001, name="Attack Boost", max_level=7)
        skill_b = Skill.objects.create(game_id=9002, name="Critical Eye", max_level=7)
        deco_a = Decoration.objects.create(game_id=510, name="Attack Jewel 1", slot=1)
        DecorationSkill.objects.create(decoration=deco_a, skill=skill_a, level=1)
        deco_b = Decoration.objects.create(game_id=511, name="Crit Jewel 1", slot=1)
        DecorationSkill.objects.create(decoration=deco_b, skill=skill_b, level=2)

        response = self.client.get(
            reverse("core:set_builder"),
            {
                "head": armor.pk,
                "decohead-0": deco_a.pk,
                "decohead-1": deco_b.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attack Jewel 1")
        self.assertContains(response, "Crit Jewel 1")
        self.assertContains(response, "Attack Boost")
        self.assertContains(response, "Critical Eye")
        self.assertRegex(response.content.decode(), r"Slots:.*?>2</span>")

    def test_armor_picker_returns_pieces(self):
        Armor.objects.create(
            game_id=7100,
            name="Rathalos Helm",
            type="head",
            rank="high",
            defense_max=60,
            slots=[3, 1],
        )
        response = self.client.get(
            reverse("core:armor_picker"), {"slot": "head"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rathalos Helm")
        self.assertContains(response, "60 def")

    def test_armor_picker_respects_slot(self):
        Armor.objects.create(game_id=7101, name="Leg Piece", type="legs", rank="high")
        response = self.client.get(
            reverse("core:armor_picker"), {"slot": "head"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Leg Piece")

    def test_charm_search_returns_matches(self):
        Charm.objects.create(game_id=700, name="Attack Charm 1")
        response = self.client.get(
            reverse("core:charm_search"), {"q": "attack"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attack Charm 1")

    def test_set_builder_page_has_charm_search(self):
        response = self.client.get(reverse("core:set_builder"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "charm-search")

    def test_monster_search_finds_rathalos(self):
        response = self.client.get(
            reverse("core:monster_list"), {"q": "rath"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rathalos")

    def test_set_builder_returns_200(self):
        response = self.client.get(reverse("core:set_builder"))
        self.assertEqual(response.status_code, 200)

    def test_optimizer_finds_sets(self):
        skill = Skill.objects.create(game_id=2, name="Attack Boost", max_level=7)
        for slot in SLOT_ORDER:
            armor = Armor.objects.create(
                game_id=3000 + len(Armor.objects.all()),
                name=f"Opt {slot}",
                type=slot,
                rank="master",
                defense_max=50,
            )
            ArmorSkill.objects.create(armor=armor, skill=skill, level=2)
        response = self.client.get(
            reverse("core:set_optimizer"),
            {"skill1_name": "Attack Boost", "skill1_level": 7},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attack Boost")

    def test_monster_detail_shows_hitzone_section(self):
        response = self.client.get(
            reverse("core:monster_detail", args=[self.monster.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Body hitzones")
