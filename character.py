from animation import Animation

class Character(Animation):
    def __init__(self, pos_x, pos_y, json_file):
        super().__init__(json_file)
        
        # self.hp = hp
        # self.ki = ki
        self.speed = 4
        self.position = [pos_x, pos_y]
        
    def update(self):
        self.rect.topleft = self.position
    
    def walk(self, side, speed):
        self.side = side
        
        if(self.side == "Right"):
            self.position[0] += self.speed

        elif(self.side == "Left"):
            self.position[0] -= self.speed

        elif(self.side == "Down"):
            self.position[1] += self.speed

        elif(self.side == "Up"):
            self.position[1] -= self.speed
            
        else:
            pass
            
    def run():
        pass
    
    def attack():
        pass
            
    def animate(self, animation_macro, animation_nbr):
        super().animate(animation_macro, animation_nbr)
        macro, side = animation_macro.split()
        
        if macro == "Walk":
            self.walk(side, self.speed)
        else:
            pass
