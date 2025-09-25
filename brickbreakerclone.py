import sys
import math
import random
import pygame

WIDTH, HEIGHT = 800, 600
FPS = 60

PADDLE_WIDTH, PADDLE_HEIGHT = 110, 18
PADDLE_SPEED = 7.0

BALL_RADIUS = 9
BALL_SPEED = 5.0
BALL_SPEED_INC_ON_BRICK = 0.04  # slight increase per brick hit
BALL_SPEED_MAX = 10.0

BRICK_ROWS_START = 5
BRICK_COLS = 10
BRICK_GAP = 4
BRICK_TOP_OFFSET = 80
BRICK_HEIGHT = 24
BRICK_SIDE_MARGIN = 30

LIVES_START = 3

BG_COLOR = (16, 18, 22)
FG_COLOR = (230, 230, 235)
PADDLE_COLOR = (245, 245, 250)
BALL_COLOR = (255, 215, 0)
TEXT_MUTED = (180, 185, 195)

# Brick colors by strength
BRICK_COLORS = {
    1: (70, 170, 255),
    2: (255, 120, 90),
    3: (140, 230, 120),
}

pygame.init()
pygame.display.set_caption("Brick Breaker")
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont("arial", 20)
BIG_FONT = pygame.font.SysFont("arial", 42, bold=True)



def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def draw_text(surface, text, font, color, center):
    img = font.render(text, True, color)
    rect = img.get_rect(center=center)
    surface.blit(img, rect)


# Game objects
class Paddle:
    def __init__(self):
        self.w = PADDLE_WIDTH
        self.h = PADDLE_HEIGHT
        self.rect = pygame.Rect((WIDTH - self.w) // 2, HEIGHT - 60, self.w, self.h)
        self.vx = 0

    def update(self, keys, mouse_x=None):
        self.vx = 0
        # Keyboard control
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -PADDLE_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = PADDLE_SPEED

        # Mouse control (if mouse moved recently, it takes precedence)
        if mouse_x is not None:
            self.rect.centerx = mouse_x
        else:
            self.rect.x += self.vx

        self.rect.x = clamp(self.rect.x, 0, WIDTH - self.w)

    def draw(self, surf):
        pygame.draw.rect(surf, PADDLE_COLOR, self.rect, border_radius=6)


class Ball:
    def __init__(self):
        self.reset()

    def reset(self, attach_to=None):
        self.x = WIDTH // 2
        self.y = HEIGHT // 2 + 60
        angle = random.uniform(-0.8, 0.8)
        speed = BALL_SPEED
        self.vx = speed * math.cos(angle)
        self.vy = -abs(speed * math.sin(angle)) - 4  # bias upward
        self.radius = BALL_RADIUS
        self.attached = False
        self.attach_target = attach_to

    def attach_to_paddle(self, paddle):
        self.attached = True
        self.attach_target = paddle

    def launch_from_paddle(self):
        if self.attached and self.attach_target:
            self.attached = False
            self.x = self.attach_target.rect.centerx
            self.y = self.attach_target.rect.top - self.radius - 1
            self.vx = random.choice([-1, 1]) * BALL_SPEED * 0.8
            self.vy = -BALL_SPEED

    def update(self):
        if self.attached and self.attach_target:
            self.x = self.attach_target.rect.centerx
            self.y = self.attach_target.rect.top - self.radius - 1
            return

        self.x += self.vx
        self.y += self.vy

        # Wall collisions
        if self.x - self.radius <= 0:
            self.x = self.radius
            self.vx *= -1
        if self.x + self.radius >= WIDTH:
            self.x = WIDTH - self.radius
            self.vx *= -1
        if self.y - self.radius <= 0:
            self.y = self.radius
            self.vy *= -1

    def speed_up(self, inc=BALL_SPEED_INC_ON_BRICK):
        speed = math.hypot(self.vx, self.vy)
        speed = min(BALL_SPEED_MAX, speed + inc)
        ang = math.atan2(self.vy, self.vx)
        self.vx = speed * math.cos(ang)
        self.vy = speed * math.sin(ang)

    def reflect_from_rect(self, rect):
        # Compute nearest point on rect to ball center
        nearest_x = clamp(self.x, rect.left, rect.right)
        nearest_y = clamp(self.y, rect.top, rect.bottom)
        dx = self.x - nearest_x
        dy = self.y - nearest_y

        # If inside overlap region, decide reflection axis by penetration
        overlap_x = self.radius - abs(dx)
        overlap_y = self.radius - abs(dy)

        if overlap_x < overlap_y:
            # Reflect horizontally
            if dx == 0:
                self.vx *= -1
            else:
                self.vx *= -1
            # Push out
            if dx < 0:
                self.x = rect.left - self.radius
            else:
                self.x = rect.right + self.radius
        else:
            # Reflect vertically
            if dy == 0:
                self.vy *= -1
            else:
                self.vy *= -1
            # Push out
            if dy < 0:
                self.y = rect.top - self.radius
            else:
                self.y = rect.bottom + self.radius

    def draw(self, surf):
        pygame.draw.circle(surf, BALL_COLOR, (int(self.x), int(self.y)), self.radius)

    def out_of_bounds(self):
        return self.y - self.radius > HEIGHT


class Brick:
    def __init__(self, rect, strength=1):
        self.rect = rect
        self.strength = strength
        self.alive = True

    def hit(self):
        self.strength -= 1
        if self.strength <= 0:
            self.alive = False

    def color(self):
        return BRICK_COLORS.get(self.strength, (200, 200, 200))

    def draw(self, surf):
        if not self.alive:
            return
        pygame.draw.rect(surf, self.color(), self.rect, border_radius=6)
        # Subtle inner highlight
        inner = self.rect.inflate(-6, -6)
        pygame.draw.rect(surf, (255, 255, 255, 20), inner, width=2, border_radius=5)


class Level:
    def __init__(self, index=1):
        self.index = index
        self.bricks = []
        self.score_value = 0
        self._generate()

    def _generate(self):
        rows = BRICK_ROWS_START + (self.index - 1)  # add a row every level
        total_gap_w = (BRICK_COLS - 1) * BRICK_GAP
        area_w = WIDTH - BRICK_SIDE_MARGIN * 2 - total_gap_w
        brick_w = area_w // BRICK_COLS

        self.bricks.clear()
        for r in range(rows):
            for c in range(BRICK_COLS):
                x = BRICK_SIDE_MARGIN + c * (brick_w + BRICK_GAP)
                y = BRICK_TOP_OFFSET + r * (BRICK_HEIGHT + BRICK_GAP)
                strength = 1 + (r // 2) + (self.index // 2)  # gets harder gradually
                strength = min(3, strength)
                rect = pygame.Rect(x, y, brick_w, BRICK_HEIGHT)
                self.bricks.append(Brick(rect, strength))
        # Score value roughly scales with bricks and strength
        self.score_value = sum(b.strength for b in self.bricks) * 10

    def alive_bricks(self):
        return [b for b in self.bricks if b.alive]

    def draw(self, surf):
        for b in self.alive_bricks():
            b.draw(surf)


# Main game state 
class Game:
    def __init__(self):
        self.reset(hard=True)

    def reset(self, hard=False):
        self.paddle = Paddle()
        self.ball = Ball()
        self.level_index = 1 if hard else getattr(self, "level_index", 1)
        self.level = Level(self.level_index)
        self.score = 0 if hard else getattr(self, "score", 0)
        self.lives = LIVES_START if hard else getattr(self, "lives", LIVES_START)
        self.state = "ready"  # ready, playing, life_lost, level_cleared, game_over, win
        self.ball.attach_to_paddle(self.paddle)
        self.mouse_x_cache = None

    def next_level(self):
        self.level_index += 1
        self.level = Level(self.level_index)
        self.ball.reset()
        self.ball.attach_to_paddle(self.paddle)
        self.state = "ready"

    def lose_life(self):
        self.lives -= 1
        if self.lives <= 0:
            self.state = "game_over"
        else:
            self.ball.reset()
            self.ball.attach_to_paddle(self.paddle)
            self.state = "ready"

    def update(self):
        keys = pygame.key.get_pressed()

        # Read mouse movement if any
        mouse_x = None
        if pygame.mouse.get_focused():
            mx, _ = pygame.mouse.get_pos()
            if self.mouse_x_cache is None or mx != self.mouse_x_cache:
                mouse_x = mx
            self.mouse_x_cache = mx

        self.paddle.update(keys, mouse_x)

        if self.state in ("ready", "playing"):
            self.ball.update()

            # Launch with Space or click
            if self.state == "ready":
                if keys[pygame.K_SPACE] or pygame.mouse.get_pressed(num_buttons=3)[0]:
                    self.ball.launch_from_paddle()
                    self.state = "playing"

            # Paddle collision (only when moving downward)
            if self.state == "playing":
                ball_rect = pygame.Rect(
                    int(self.ball.x - self.ball.radius),
                    int(self.ball.y - self.ball.radius),
                    self.ball.radius * 2,
                    self.ball.radius * 2,
                )

                if self.ball.vy > 0 and ball_rect.colliderect(self.paddle.rect):
                    # Calculate hit position to vary bounce angle
                    offset = (self.ball.x - self.paddle.rect.centerx) / (self.paddle.w / 2)
                    offset = clamp(offset, -1, 1)
                    speed = max(6.0, min(BALL_SPEED_MAX, math.hypot(self.ball.vx, self.ball.vy)))
                    angle = -math.pi / 3 * offset  # -60° to +60°
                    self.ball.vx = speed * math.sin(angle)
                    self.ball.vy = -abs(speed * math.cos(angle))
                    # Nudge ball above paddle to avoid sticky collisions
                    self.ball.y = self.paddle.rect.top - self.ball.radius - 1

                # Brick collisions
                hit_any = False
                for brick in self.level.alive_bricks():
                    if ball_rect.colliderect(brick.rect):
                        hit_any = True
                        brick.hit()
                        self.ball.reflect_from_rect(brick.rect)
                        self.ball.speed_up()
                        self.score += 10
                        break  # one brick per frame for stability

                if hit_any and not self.level.alive_bricks():
                    self.state = "level_cleared"

                # Life lost
                if self.ball.out_of_bounds():
                    self.lose_life()

        elif self.state in ("level_cleared", "game_over"):
            pass  # wait for user input handled in handle_event()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.reset(hard=True)
            if event.key == pygame.K_SPACE:
                if self.state == "level_cleared":
                    self.next_level()
                elif self.state == "game_over":
                    self.reset(hard=True)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.state == "level_cleared":
                self.next_level()
            elif self.state == "game_over":
                self.reset(hard=True)

    def draw_hud(self, surf):
        # Top bar text
        draw_text(surf, f"Score: {self.score}", FONT, FG_COLOR, (80, 24))
        draw_text(surf, f"Lives: {self.lives}", FONT, FG_COLOR, (WIDTH - 80, 24))
        draw_text(surf, f"Level: {self.level_index}", FONT, FG_COLOR, (WIDTH // 2, 24))

    def draw_state_overlay(self, surf):
        if self.state == "ready":
            draw_text(surf, "Move: Mouse / Arrow Keys | Launch: Space/Click", FONT, TEXT_MUTED, (WIDTH // 2, HEIGHT // 2 + 24))
            draw_text(surf, "Press Space or Click to Launch", BIG_FONT, FG_COLOR, (WIDTH // 2, HEIGHT // 2 - 16))
        elif self.state == "level_cleared":
            draw_text(surf, "Level Cleared!", BIG_FONT, FG_COLOR, (WIDTH // 2, HEIGHT // 2 - 16))
            draw_text(surf, "Press Space or Click for Next Level", FONT, TEXT_MUTED, (WIDTH // 2, HEIGHT // 2 + 24))
        elif self.state == "game_over":
            draw_text(surf, "Game Over", BIG_FONT, FG_COLOR, (WIDTH // 2, HEIGHT // 2 - 16))
            draw_text(surf, "Press Space or Click to Restart", FONT, TEXT_MUTED, (WIDTH // 2, HEIGHT // 2 + 24))

    def draw(self, surf):
        surf.fill(BG_COLOR)
        self.level.draw(surf)
        self.paddle.draw(surf)
        self.ball.draw(surf)
        self.draw_hud(surf)
        if self.state in ("ready", "level_cleared", "game_over"):
            self.draw_state_overlay(surf)


# Main loop
def main():
    game = Game()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            game.handle_event(event)

        game.update()
        game.draw(SCREEN)

        pygame.display.flip()
        CLOCK.tick(FPS)


if __name__ == "__main__":
    main()
