from animation import AnimationDirection
from character import Character


class SuperSaiyanMixin:
    """Gives a Character the Super Saiyan transformations.

    A character can have several levels (Goku: SSJ and SSJ3, one sheet
    each); the selected one is used by transform(). Used by the playable
    Saiyan and by Saiyan NPCs (see npc.SaiyanNPC).
    """

    TRANSFORM_CLOCK_SPEED = 20
    TRANSFORM_HOLD_TICKS = 10
    # Ki needed to transform into each level
    TRANSFORM_MIN_KI = {"ssj": 20, "ssj2": 28, "ssj3": 35}
    LEVEL_NAMES = {"ssj": "SSJ", "ssj2": "SSJ2", "ssj3": "SSJ3"}

    can_transform = True

    @property
    def super_levels(self):
        """The Super Saiyan forms this character has sheets for."""
        return [form for form in self.SUPER_FORMS if self.has_form(form)]

    @property
    def target_level(self):
        """The level transform() goes to."""
        levels = self.super_levels
        if not levels:
            return None
        return levels[getattr(self, "selected_level", 0) % len(levels)]

    def cycle_level(self, step):
        levels = self.super_levels
        if levels:
            self.selected_level = (getattr(self, "selected_level", 0) + step) % len(levels)

    def transform(self):
        """Transform into the selected level; at that level already, go back
        to normal. Returns True if something happened."""
        if self.action is not None or self.hp <= 0:
            return False
        target = self.target_level
        if self.is_super and (target is None or self.form == target):
            if not self.can_revert:
                return False
            self.revert()
            return True
        if target is None or self.ki < self.TRANSFORM_MIN_KI.get(target, 20):
            return False

        # The level's own transformation sprites when its sheet has them
        # (SSJ3), else the ones of the current form (base -> SSJ)
        on_done = lambda: self._become_super(target)
        if self.forms[target].frame_count("Transform"):
            self.set_form(target)
        if not self.start_action(
            "transform",
            "Transform",
            self.TRANSFORM_CLOCK_SPEED,
            hold_ticks=self.TRANSFORM_HOLD_TICKS,
            on_done=on_done,
        ):
            # No transformation sprites: change form right away
            on_done()
            self.face_idle()
        return True

    def _become_super(self, form=None):
        self.set_form(form or self.target_level or self.SUPER_FORM)
        self.facing = AnimationDirection.DOWN.value
        self.animation_name = "IDLE Down"


class Saiyan(SuperSaiyanMixin, Character):
    """Playable Saiyan."""

    def __init__(self, pos_x, pos_y, is_transformed, name):
        super().__init__(pos_x, pos_y, name)
        self.selected_level = 0
        if is_transformed:
            self._become_super()
            self.face_idle()
