"""Epic Fights: the story mode's great battles (Config/epic_fights.json).

Each fight has its heroes (the player's character, the Super Saiyan level
it starts at, its allies), its enemies coming in waves (the first one's
leader is the boss), an arena, its music and a few lines before it starts.
Alone, the player is the hero and the computer runs everyone else; online,
the host plays the hero's side and the other player the boss's (the boss
and the rest of the first wave as its allies).

Which fights the player has won is saved with the settings.
"""

import json
import os
from dataclasses import dataclass, field

import arenas
import roster
import settings as user_settings
from utils.config import Config

# At most this many enemies at once (map.EPIC_MAX_ENEMIES), allies
# (EPIC_MAX_ALLIES); online, a side has at most ONLINE_ALLIES allies
MAX_WAVE = 14
MAX_ALLIES = 7
ONLINE_ALLIES = 3
CLEARED_KEY = "epic_cleared"


@dataclass
class Quest:
    """What an Epic Fight asks besides beating everyone:
        survive    hold out this many seconds: then it is won (beating
                   everyone before also wins)
        protect    allies who must not be knocked out (else it is lost)
        finisher   the technique the boss must be beaten with: any other
                   hit leaves it standing (at 1 HP)"""
    survive: float = 0
    protect: list = field(default_factory=list)
    finisher: str = None

    @classmethod
    def from_entry(cls, entry):
        if not isinstance(entry, dict):
            return cls()
        return cls(survive=float(entry.get("survive", 0) or 0),
                   protect=[str(name) for name in entry.get("protect", [])],
                   finisher=str(entry["finisher"]) if entry.get("finisher") else None)

    def lines(self, boss=None, technique_name=None):
        """The quest in words (the versus card, the objective panel)."""
        from roster import display_name
        lines = []
        if self.survive:
            lines.append(f"Survive for {int(self.survive)} seconds")
        for name in self.protect:
            lines.append(f"{display_name(name)} must survive")
        if self.finisher:
            what = technique_name or self.finisher.replace("_", " ").title()
            lines.append(f"Finish {display_name(boss) if boss else 'the boss'} with the {what}")
        if not lines:
            lines.append("Defeat every enemy")
        return lines


@dataclass
class Fight:
    id: str
    title: str
    subtitle: str
    hero: str
    waves: list
    arena: str = arenas.DEFAULT
    form: str = None
    allies: list = field(default_factory=list)
    boss_form: str = None
    # The allies' starting Super Saiyan levels ({name: form})
    ally_forms: dict = field(default_factory=dict)
    # What it takes to win (see Quest)
    quest: "Quest" = None
    # Who the versus card and the list show against the heroes (the boss,
    # unless another one: Android 13, not the first wave's Android 19)
    face_of: str = None

    @property
    def face(self):
        return self.face_of or self.boss
    music: str = None
    intro: list = field(default_factory=list)

    @property
    def boss(self):
        return self.waves[0][0]

    def side(self, slot):
        """(character, form, allies) of a side: 0 the hero's, 1 the boss's."""
        if slot == 0:
            return self.hero, self.form, list(self.allies)
        return self.boss, self.boss_form, list(self.waves[0][1:1 + ONLINE_ALLIES])


_fights = None


def _load():
    path = os.path.join(Config.ROOT_DIR, "Config", "epic_fights.json")
    try:
        with open(path, encoding="utf-8") as file:
            entries = json.load(file).get("fights", [])
    except (OSError, ValueError):
        return []
    fights = []
    for entry in entries:
        try:
            waves = [[str(name) for name in wave][:MAX_WAVE] for wave in entry["waves"] if wave]
            fight = Fight(id=str(entry["id"]), title=str(entry["title"]), subtitle=str(entry.get("subtitle", "")),
                          hero=str(entry["hero"]), waves=waves, arena=str(entry.get("arena", arenas.DEFAULT)),
                          form=entry.get("form"), allies=[str(name) for name in entry.get("allies", [])][:MAX_ALLIES],
                          boss_form=entry.get("boss_form"), music=entry.get("music"),
                          ally_forms={str(k): str(v) for k, v in entry.get("ally_forms", {}).items()},
                          quest=Quest.from_entry(entry.get("quest")),
                          face_of=str(entry["face"]) if entry.get("face") else None,
                          intro=[(str(who), str(line)) for who, line in entry.get("intro", [])])
        except (KeyError, TypeError, ValueError):
            continue
        if fight.waves:
            fights.append(fight)
    return fights


def all_fights():
    """Every fight of the file, in order."""
    global _fights
    if _fights is None:
        _fights = _load()
    return _fights


def playable(fight):
    """Whether everyone in the fight is installed (sheets) and its arena
    exists here."""
    names = {fight.hero, *fight.allies, *(name for wave in fight.waves for name in wave)}
    return all(roster.installed(name) for name in names) and fight.arena in arenas.available()


def fights():
    """The fights that can be played on this install."""
    return [fight for fight in all_fights() if playable(fight)]


def by_id(fight_id):
    return next((fight for fight in all_fights() if fight.id == fight_id), None)


def cleared():
    """The ids of the fights the player has won."""
    saved = user_settings.load().get(CLEARED_KEY)
    return set(saved) if isinstance(saved, list) else set()


def mark_cleared(fight):
    settings = user_settings.load()
    done = cleared() | {fight.id}
    settings[CLEARED_KEY] = sorted(done)
    user_settings.save(settings)


def next_fight(fight):
    """The fight after this one, or None after the last."""
    playing = fights()
    ids = [f.id for f in playing]
    if fight.id not in ids:
        return None
    index = ids.index(fight.id) + 1
    return playing[index] if index < len(playing) else None


def start_in_form(character, form):
    """A fighter starting a fight at a Super Saiyan level (an Epic Fight's
    hero or boss), if it has that form."""
    if not form or not character.has_form(form):
        return
    character.set_form(form)
    levels = getattr(character, "super_levels", [])
    if form in levels:
        character.selected_level = levels.index(form)
    character.face_idle()


# In an Epic Fight the enemies are stronger (more HP, harder hits) and the
# player's allies a little weaker: they cannot win it alone
ENEMY_STRENGTH = 1.5
ALLY_STRENGTH = 0.8


def strengthen(fighter, factor, health=True):
    """Make an NPC factor times as strong: its hits and techniques (and its
    health, when health)."""
    fighter.attack_damage *= factor
    fighter.technique_damage = getattr(fighter, "technique_damage", 1.0) * factor
    if health:
        fighter.max_hp = round(fighter.max_hp * factor)
        fighter.hp = fighter.max_hp


# Enemies whose strength an Epic Fight sets against other fighters instead:
# a Cell Jr. is twice as strong as the Z Warriors, as they fight beside the
# player in an Epic Fight (their hits, techniques, health, defense)
STRONGER_THAN = {"cell_jr": (2.0, ("krillin", "tien", "yamcha"))}


def strengthen_enemy(enemy):
    """An Epic Fight's enemy: ENEMY_STRENGTH times as strong, or, for one of
    STRONGER_THAN, that many times as strong as those fighters are as the
    player's allies in an Epic Fight."""
    rule = STRONGER_THAN.get(enemy.character_name)
    if rule is None:
        strengthen(enemy, ENEMY_STRENGTH)
        return
    from npc import HEROES, SaiyanNPC
    times, others = rule
    allies = []
    for name in others:
        ally = SaiyanNPC(0, 0, False, name, 0, [], team=HEROES)
        strengthen(ally, ALLY_STRENGTH, health=False)
        allies.append(ally)

    def average(attribute):
        return sum(getattr(ally, attribute) for ally in allies) / len(allies)

    enemy.attack_damage = times * average("attack_damage")
    enemy.technique_damage = times * average("technique_damage")
    enemy.max_hp = round(times * average("max_hp"))
    enemy.hp = enemy.max_hp
    enemy.damage_taken = average("damage_taken") / times


def lock_form(fighter):
    """In an Epic Fight the allies and the enemies stay in the form the
    fight gives them: no powering up, no fusion, no absorption."""
    fighter.form_locked = True


def reset():
    """Read the file again (tests)."""
    global _fights
    _fights = None
