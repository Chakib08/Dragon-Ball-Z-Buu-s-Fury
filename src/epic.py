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


def reset():
    """Read the file again (tests)."""
    global _fights
    _fights = None
