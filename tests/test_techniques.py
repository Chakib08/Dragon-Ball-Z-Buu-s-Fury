import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat import CombatSystem
from effects import Beam, Burst, ChargeGlow, Projectile
from npc import NPC
from saiyan import Saiyan
from techniques import background_shades
from touch_controls import TouchControls
from utils.config import Config

from average_stats import steady_module_fixtures

# Repeatable NPCs: no lucky dodges or blocks (see average_stats.py)
setUpModule, tearDownModule = steady_module_fixtures()


EXPECTED = {
    "goku": ["Energy Blast", "Kamehameha", "Instant Transmission", "Potara Fusion"],
    "gohan": ["Energy Blast", "Kamehameha", "Ki Burst"],
    "vegeta": ["Energy Blast", "Final Flash", "Big Bang Attack", "Potara Fusion"],
    "trunks": ["Energy Blast", "Burning Attack", "Sword Slash"],
    "broly": ["Energy Blast", "Eraser Cannon", "Blaster Shell"],
    "piccolo": ["Energy Blast", "Special Beam Cannon", "Ki Burst"],
    "android17": ["Energy Blast", "Power Blitz", "Barrier"],
    "android18": ["Energy Blast", "Destructo Disc", "Barrier"],
    "goten": ["Energy Blast", "Kamehameha", "Ki Burst"],
    "kid_trunks": ["Energy Blast", "Burning Attack", "Ki Burst"],
    "gotenks": ["Energy Blast", "Super Ghost Kamikaze Attack", "Galactic Donut"],
    "great_saiyaman": ["Energy Blast", "Kamehameha", "Ki Burst"],
    "vegito": ["Energy Blast", "Final Kamehameha", "Spirit Sword"],
    "cell_imperfect": ["Energy Blast", "Kamehameha", "Absorb Android 17"],
    "cell_semi_perfect": ["Energy Blast", "Kamehameha", "Absorb Android 18"],
    "cell_perfect": ["Energy Blast", "Kamehameha", "Perfect Barrier"],
    "buu": ["Energy Blast", "Candy Beam", "Steam Rage"],
    "super_buu": ["Energy Blast", "Human Extinction Attack", "Steam Rage"],
    "super_buu_gotenks": ["Energy Blast", "Human Extinction Attack", "Steam Rage"],
    "super_buu_gohan": ["Energy Blast", "Human Extinction Attack", "Steam Rage"],
    "kid_buu": ["Energy Blast", "Planet Burst", "Steam Rage"],
}


class TechniqueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def setUp(self):
        self.now = 10_000
        for target in ("combat", "character", "npc"):
            patcher = patch(f"{target}.pygame.time.get_ticks", side_effect=lambda: self.now)
            patcher.start()
            self.addCleanup(patcher.stop)

    def fighters(self, name="goku", gap=70, dy=0, enemy_name="gohan"):
        player = Saiyan(100, 100, False, name)
        player.update()
        player.facing = "Right"
        enemy = NPC(0, 0, False, enemy_name, 0, [])
        enemy.position = [player.feet.centerx + gap - enemy.rect.width / 2,
                          player.feet.bottom + dy - enemy.rect.height]
        enemy.update()
        enemy.facing = "Left"
        # It must not interrupt the player's techniques by hitting back
        enemy.attack_damage = 0
        combat = CombatSystem(player, (1200, 540))
        return player, enemy, combat

    def run_frames(self, player, enemy, combat, frames=250):
        for _ in range(frames):
            self.now += 17
            player.update_action()
            combat.update([], [], opponents=[enemy])

    def use(self, combat, index):
        combat.selected_technique = index
        combat.player.ki = combat.player.max_ki
        return combat.start_special()

    def test_each_character_has_its_three_techniques_with_sprites_for_each_form(self):
        for name, names in EXPECTED.items():
            player = Saiyan(0, 0, False, name)
            self.assertEqual([t.name for t in player.techniques], names, name)
            for technique in player.techniques:
                if technique.kind == "evolve":
                    continue  # no sprites of its own (see evolution.py)
                for form in player.forms:
                    with self.subTest(character=name, form=form, technique=technique.name):
                        player.set_form(form)
                        sprites = technique.form_for(player)
                        self.assertIsNotNone(sprites)
                        for direction in ("Down", "Right", "Left", "Up"):
                            frames = player.frames(technique.pose_macro(direction))
                            self.assertTrue(frames)
                            self.assertTrue(all(f.get_width() > 0 for f in frames))

    def test_effects_from_the_shared_sheet_are_transparent_around_the_sprite(self):
        """The effects sheet of dbz-assets puts each frame on a cell of its
        own shade: that shade, never a colour of the sprite, is see-through."""
        for name in ("trunks", "broly"):
            player = Saiyan(0, 0, False, name)
            for technique in player.techniques:
                sprites = technique.form_for(player)
                for key in ("projectile", "hit", "grow", "rings"):
                    for image in sprites.cuts(key):
                        with self.subTest(character=name, technique=technique.name, part=key):
                            width, height = image.get_size()
                            key_colour = tuple(image.get_colorkey()[:3])
                            self.assertIn(key_colour, background_shades(sprites.sheet))
                            border = [tuple(image.get_at((x, y))[:3]) for x in range(width) for y in (0, height - 1)]
                            self.assertIn(key_colour, border)

    def test_projectile_hits_the_enemy_in_front_and_misses_one_out_of_line(self):
        player, enemy, combat = self.fighters()
        self.assertTrue(self.use(combat, 0))
        self.assertEqual(player.ki, player.max_ki - combat.technique.cost)
        self.run_frames(player, enemy, combat)
        self.assertLess(enemy.hp, enemy.max_hp)

        player, enemy, combat = self.fighters(dy=60)
        self.use(combat, 0)
        self.run_frames(player, enemy, combat)
        self.assertEqual(enemy.hp, enemy.max_hp)

    def test_effects_are_sprites_of_the_right_kind(self):
        kinds = {"goku": [Projectile, Beam, None], "gohan": [Projectile, Beam, Burst],
                 "vegeta": [Projectile, Beam, Projectile]}
        for name, expected in kinds.items():
            for index, kind in enumerate(expected):
                if kind is None:
                    continue
                with self.subTest(character=name, technique=index):
                    # A bigger effect (a signature technique) needs more room
                    scale = Saiyan(0, 0, False, name).techniques[index].effect_scale
                    player, enemy, combat = self.fighters(name, gap=30 if kind is Burst else 70 * scale)
                    self.use(combat, index)
                    seen = None
                    for _ in range(160):  # long enough for a full charge
                        self.now += 17
                        player.update_action()
                        combat.update([], [], opponents=[enemy])
                        released = [e for e in combat.effects if not isinstance(e, ChargeGlow)]
                        if released:
                            seen = released[0]
                            break
                    self.assertIsInstance(seen, kind)
                    self.assertGreater(seen.image.get_width(), 0)
                    self.run_frames(player, enemy, combat)
                    self.assertLess(enemy.hp, enemy.max_hp)

    def test_beam_stops_on_the_enemy_with_its_impact(self):
        player, enemy, combat = self.fighters()
        self.use(combat, 1)
        beam = None
        for _ in range(250):
            self.now += 17
            player.update_action()
            combat.update([], [], opponents=[enemy])
            beam = beam or next((e for e in combat.effects if isinstance(e, Beam)), None)
            if beam is not None and beam.hit:
                break
        self.assertTrue(beam.hit)
        self.assertLess(beam.length, beam.max_range)

    def test_ki_burst_only_hits_close_enemies(self):
        for gap, hit in ((30, True), (90, False)):
            with self.subTest(gap=gap):
                player, enemy, combat = self.fighters("gohan", gap=gap)
                self.use(combat, 2)
                self.run_frames(player, enemy, combat)
                self.assertEqual(enemy.hp < enemy.max_hp, hit)

    def test_instant_transmission_appears_next_to_the_enemy_and_strikes(self):
        player, enemy, combat = self.fighters("goku", gap=120)
        combat.update([], [], opponents=[enemy])
        self.use(combat, 2)
        self.run_frames(player, enemy, combat, frames=80)
        distance = ((player.feet.centerx - enemy.feet.centerx) ** 2
                    + (player.feet.centery - enemy.feet.centery) ** 2) ** 0.5
        self.assertLess(distance, 30)
        self.assertLess(enemy.hp, enemy.max_hp)

    def test_instant_transmission_never_lands_inside_a_big_enemy(self):
        player, enemy, combat = self.fighters("goku", gap=120, enemy_name="broly")
        combat.update([], [], opponents=[enemy])
        self.use(combat, 2)
        self.run_frames(player, enemy, combat, frames=80)
        self.assertFalse(player.body.colliderect(enemy.body))
        self.assertLess(enemy.hp, enemy.max_hp)

    def charge_and_release(self, name, index, charge_ms, gap=70):
        """Charge for charge_ms (or until it goes by itself), then return the
        released effect and the damage it did."""
        player, enemy, combat = self.fighters(name, gap=gap)
        self.use(combat, index)
        self.assertTrue(combat.charging)
        self.assertEqual(player.action["name"], "charging")
        start = self.now
        while combat.charging and self.now - start < charge_ms:
            self.now += 17
            player.update_action()
            combat.update([], [], opponents=[enemy])
        combat.release_charge()
        effect = None
        for _ in range(200):
            self.now += 17
            player.update_action()
            combat.update([], [], opponents=[enemy])
            effect = effect or next((e for e in combat.effects if not isinstance(e, ChargeGlow)), None)
        return effect, enemy.max_hp - enemy.hp

    def test_charge_glow_grows_in_the_hands_while_held(self):
        player, enemy, combat = self.fighters("goku")
        self.use(combat, 1)
        glow = next(e for e in combat.effects if isinstance(e, ChargeGlow))
        sizes = []
        for _ in range(60):
            self.now += 17
            player.update_action()
            combat.update([], [], opponents=[enemy])
            sizes.append(glow.image.get_width())
        self.assertGreater(max(sizes[-10:]), sizes[0])
        self.assertTrue(combat.charging)
        self.assertGreater(combat.charge_level, 0.5)

    def test_a_longer_charge_is_bigger_and_stronger(self):
        for name, index in (("goku", 1), ("vegeta", 2)):
            with self.subTest(character=name):
                gap = 70 * Saiyan(0, 0, False, name).techniques[index].effect_scale
                quick, quick_damage = self.charge_and_release(name, index, 100, gap)
                full, full_damage = self.charge_and_release(name, index, 10_000, gap)
                self.assertGreater(full_damage, quick_damage)
                self.assertGreater(full.image.get_height() if isinstance(full, Projectile) else full.pieces["heads"][0].get_height(),
                                   quick.image.get_height() if isinstance(quick, Projectile) else quick.pieces["heads"][0].get_height())

    def test_signature_techniques_are_twice_as_big_and_reach_four_times_farther(self):
        from effects import build_effect
        from techniques import STATS
        signature = {"goku": ["kamehameha"], "gohan": ["kamehameha"], "vegeta": ["final_flash", "big_bang"]}
        for name, ids in signature.items():
            player = Saiyan(100, 100, False, name)
            player.update()
            for technique in player.techniques:
                with self.subTest(character=name, technique=technique.id):
                    usual = STATS[technique.kind]
                    big = technique.id in ids
                    self.assertEqual(technique.effect_scale, 2.0 if big else 1.0)
                    self.assertEqual(technique.stats.get("range"),
                                     usual.get("range") * 4 if big and "range" in usual else usual.get("range"))
                    if not big or technique.kind == "teleport":
                        continue
                    sprites = technique.form_for(player)
                    effect = build_effect(technique, sprites, player, "Right", 0, None, lambda e: None)
                    technique.effect_scale = 1.0
                    plain = build_effect(technique, sprites, player, "Right", 0, None, lambda e: None)
                    technique.effect_scale = 2.0
                    size = (lambda e: e.pieces["heads"][0].get_height()) if technique.kind == "beam" \
                        else (lambda e: e.frames[0].get_height())
                    self.assertAlmostEqual(size(effect) / size(plain), 2, delta=0.1)
        # Everyone else's techniques are as before
        trunks = Saiyan(0, 0, False, "trunks")
        self.assertTrue(all(t.effect_scale == 1.0 for t in trunks.techniques))
        # The shared table is untouched
        self.assertEqual(STATS["beam"]["range"], 230)

    def test_ssj3_kamehameha_is_bigger_and_stronger_than_ssj(self):
        from effects import build_effect
        heads, damage = {}, {}
        for level in (0, 1):
            player, enemy, combat = self.fighters()
            player.selected_level = level
            player.ki = player.max_ki
            player.transform()
            while player.update_action():
                pass
            kamehameha = player.techniques[1]
            beam = build_effect(kamehameha, kamehameha.form_for(player), player, "Right", 0,
                                None, lambda effect: None, power=1.0)
            heads[player.form] = beam.pieces["heads"][0].get_height()
            damage[player.form] = combat.damage_multiplier(player)
        self.assertGreater(heads["ssj3"], heads["ssj"])
        self.assertGreater(damage["ssj3"], damage["ssj"])

    def test_full_charge_releases_by_itself(self):
        player, enemy, combat = self.fighters("gohan")
        self.use(combat, 1)
        for _ in range(int(combat.CHARGE_MS / 17) + 3):
            self.now += 17
            player.update_action()
            combat.update([], [], opponents=[enemy])
        self.assertFalse(combat.charging)
        self.assertEqual(player.action["name"], "special")

    def test_getting_hit_cancels_the_charge(self):
        player, enemy, combat = self.fighters("goku")
        self.use(combat, 1)
        ki = player.ki
        player.take_damage(5)
        self.now += 17
        combat.update([], [], opponents=[enemy])
        self.assertFalse(combat.charging)
        self.assertFalse([e for e in combat.effects if isinstance(e, ChargeGlow) and not e.done])
        self.assertLess(player.ki, ki + 1)  # the ki stays spent

    def test_cost_cooldown_and_busy(self):
        player, enemy, combat = self.fighters()
        combat.selected_technique = 1
        player.ki = combat.technique.cost - 1
        self.assertFalse(combat.start_special())
        player.ki = 100
        self.assertTrue(combat.start_special())
        self.assertFalse(combat.start_special())  # busy posing
        player.action = None
        self.assertFalse(combat.start_special())  # on cooldown
        self.now += combat.technique.stats["cooldown_ms"]
        self.assertTrue(combat.start_special())

    def test_switching_techniques_wraps_around(self):
        player, enemy, combat = self.fighters()
        names = [combat.technique.name]
        for _ in range(len(EXPECTED["goku"])):
            combat.cycle_technique(1)
            names.append(combat.technique.name)
        self.assertEqual(names, EXPECTED["goku"] + ["Energy Blast"])
        combat.cycle_technique(-1)
        self.assertEqual(combat.technique.name, EXPECTED["goku"][-1])


class TechniqueControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_arrows_sit_on_top_of_the_ki_button_and_fire_once(self):
        controls = TouchControls((1200, 540))
        ki_x, ki_y = controls.buttons["special"]
        for name in ("tech_prev", "tech_next"):
            x, y = controls.arrows[name]
            self.assertLess(y, ki_y)
            self.assertEqual(controls._control_at((x, y)), name)
            event = pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=x / 1200, y=y / 540)
            controls.handle_event(event)
            self.assertTrue(controls.consume_action(name))
            self.assertFalse(controls.consume_action(name))
            controls.handle_event(pygame.event.Event(pygame.FINGERUP, finger_id=1, x=x / 1200, y=y / 540))
        self.assertLess(controls.arrows["tech_prev"][0], ki_x)
        self.assertGreater(controls.arrows["tech_next"][0], ki_x)

    def test_arrows_and_name_stay_on_screen(self):
        for size in ((1200, 540), (800, 480), (2400, 1080)):
            controls = TouchControls(size)
            screen = pygame.Surface(size)
            controls.draw(screen, "Instant Transmission")
            for name, (x, y) in controls.arrows.items():
                radius = controls.radius(name)
                self.assertTrue(pygame.Rect((0, 0), size).contains(
                    pygame.Rect(x - radius, y - radius, radius * 2, radius * 2)))


    def test_level_arrows_sit_on_the_transform_button_and_hide_without_a_choice(self):
        controls = TouchControls((1200, 540))
        transform_x, transform_y = controls.buttons["super"]
        self.assertLess(controls.arrows["form_prev"][0], transform_x)
        self.assertGreater(controls.arrows["form_next"][0], transform_x)
        self.assertLess(controls.arrows["form_prev"][1], transform_y)
        screen = pygame.Surface((1200, 540))
        controls.draw(screen, "Kamehameha", "SSJ3")
        self.assertEqual(controls._control_at(controls.arrows["form_next"]), "form_next")
        controls.draw(screen, "Kamehameha", None)
        self.assertNotEqual(controls._control_at(controls.arrows["form_next"]), "form_next")

if __name__ == "__main__":
    unittest.main()
