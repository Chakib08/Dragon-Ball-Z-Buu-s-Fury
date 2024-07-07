from character import Character


class NPC(Character):
    def __init__(self, pos_x, pos_y, isTransformed, name, nb_points):
        super().__init__(pos_x, pos_y, name)

        self.isTransofrmed = isTransformed
        self.rect = self.image.get_rect()
        self.name = name
        self.nb_points = nb_points
        self.points = []
        self.current_point = 0

    def teleport_spawn(self):
        location = self.points[self.current_point]
        self.position[0] = location.x
        self.position[1] = location.y

    def load_points(self, map):
        for i in range(self.nb_points):
            point = map.get_object(f"{self.name}_path_{i}")
            rect = map.get_rect(point)
            self.points.append(rect)
            self.save_location()


    def move_npc(self):
        current_point = self.current_point
        target_point = current_point + 1

        # Ensure target_point is within the bounds of the points list
        if target_point >= len(self.points):
            target_point = 0  # Reset to the first point or handle appropriately

        current_rect = self.points[current_point]
        target_rect = self.points[target_point]

        if current_rect.y < target_rect.y and abs(current_rect.x - target_rect.x) < 3:
            self.animate("Walk Down", 4)
        elif current_rect.y > target_rect.y and abs(current_rect.x - target_rect.x) < 3:
            self.animate("Walk Up", 4)
        elif current_rect.x > target_rect.x and abs(current_rect.y - target_rect.y) < 3:
            self.animate("Walk Left", 4)
        elif current_rect.x < target_rect.x and abs(current_rect.y - target_rect.y) < 3:
            self.animate("Walk Right", 4)

        if self.rect.colliderect(target_rect):
            self.current_point = target_point

    def animate(self, animation_macro, animation_nbr):
        super().animate(animation_macro, animation_nbr)


        # Check if the Transofrm string is in the animation macro retreived from the json file
        if "Transform" in animation_macro:
            macro, level, side = animation_macro.split()
        else:
            macro, side = animation_macro.split()

        if macro == "Walk":
            self.speed = 4
            self.move(side)
        elif macro == "Run":
            self.speed = 8
            self.move(side)
        # TODO: Implement Attack