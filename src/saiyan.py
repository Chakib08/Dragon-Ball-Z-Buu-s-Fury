from animation import AnimationDirection
from character import Character


class SuperSaiyanMixin:
    """Gives a Character the Super Saiyan transformation.

    Used by the playable Saiyan and by Saiyan NPCs (see npc.SaiyanNPC).
    """

    TRANSFORM_CLOCK_SPEED = 20
    TRANSFORM_HOLD_TICKS = 10
    TRANSFORM_MIN_KI = 20

    can_transform = True

    def transform(self):
        """Toggle Super Saiyan. Returns True if something happened."""
        if self.action is not None or self.hp <= 0:
            return False
        if self.is_super:
            self.revert()
            return True
        if not self.has_form(self.SUPER_FORM) or self.ki < self.TRANSFORM_MIN_KI:
            return False

        if not self.start_action(
            "transform",
            "Transform",
            self.TRANSFORM_CLOCK_SPEED,
            hold_ticks=self.TRANSFORM_HOLD_TICKS,
            on_done=self._become_super,
        ):
            # No transformation sprites: change form right away
            self._become_super()
            self.face_idle()
        return True

    def _become_super(self):
        self.set_form(self.SUPER_FORM)
        self.facing = AnimationDirection.DOWN.value
        self.animation_name = "IDLE Down"


class Saiyan(SuperSaiyanMixin, Character):
    """Playable Saiyan."""

    def __init__(self, pos_x, pos_y, is_transformed, name):
        super().__init__(pos_x, pos_y, name)
        if is_transformed:
            self._become_super()
            self.face_idle()
