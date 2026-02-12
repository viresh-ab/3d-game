"""Simple 3D racing game built with Ursina.

Features:
- Player-controlled 3D car with acceleration and steering.
- Oval track made from reusable road segments and border barriers.
- Third-person follow camera.
- Border collision handling with speed penalty and bounce effect.
- Lap counter and lap timer UI.

Run:
    python racing_game.py
"""

from __future__ import annotations

from dataclasses import dataclass

from ursina import (
    Ursina,
    Entity,
    Text,
    camera,
    color,
    held_keys,
    time,
    window,
    clamp,
    Vec3,
)


@dataclass
class CarConfig:
    """Configuration values that control car movement behavior."""

    acceleration: float = 26.0
    brake_acceleration: float = 40.0
    reverse_acceleration: float = 16.0
    friction: float = 14.0
    max_forward_speed: float = 25.0
    max_reverse_speed: float = 10.0
    steering_power: float = 95.0


class RaceTrack:
    """Constructs and stores race-track geometry and collision helpers."""

    def __init__(self, lane_half_width: float = 6.0, border_height: float = 0.75) -> None:
        self.outer_half_extent_x = 30.0
        self.outer_half_extent_z = 20.0
        self.inner_half_extent_x = 12.0
        self.inner_half_extent_z = 5.0
        self.lane_half_width = lane_half_width
        self.border_height = border_height

        self.road_segments: list[Entity] = []
        self.barriers: list[Entity] = []

        self._build_track()

    def _build_track(self) -> None:
        """Build a rectangular ring track and visual barriers."""
        road_color = color.rgb(80, 80, 85)
        grass_color = color.rgb(36, 105, 40)
        barrier_color = color.rgb(220, 50, 50)

        # Ground / grass plane.
        Entity(
            model="plane",
            scale=(90, 1, 70),
            texture="white_cube",
            texture_scale=(12, 10),
            color=grass_color,
            collider="box",
        )

        # Four road rectangles form a loop with an interior hole.
        outer_x = self.outer_half_extent_x
        outer_z = self.outer_half_extent_z
        inner_x = self.inner_half_extent_x
        inner_z = self.inner_half_extent_z

        self.road_segments.extend(
            [
                # Top straight
                Entity(
                    model="cube",
                    position=(0, 0.05, outer_z - (outer_z - inner_z) / 2),
                    scale=(outer_x * 2, 0.1, outer_z - inner_z),
                    color=road_color,
                ),
                # Bottom straight
                Entity(
                    model="cube",
                    position=(0, 0.05, -outer_z + (outer_z - inner_z) / 2),
                    scale=(outer_x * 2, 0.1, outer_z - inner_z),
                    color=road_color,
                ),
                # Left straight
                Entity(
                    model="cube",
                    position=(-outer_x + (outer_x - inner_x) / 2, 0.05, 0),
                    scale=(outer_x - inner_x, 0.1, inner_z * 2),
                    color=road_color,
                ),
                # Right straight
                Entity(
                    model="cube",
                    position=(outer_x - (outer_x - inner_x) / 2, 0.05, 0),
                    scale=(outer_x - inner_x, 0.1, inner_z * 2),
                    color=road_color,
                ),
            ]
        )

        # Outer barrier walls.
        self.barriers.extend(
            [
                Entity(
                    model="cube",
                    position=(0, self.border_height / 2, outer_z),
                    scale=(outer_x * 2 + 1.0, self.border_height, 1),
                    color=barrier_color,
                    collider="box",
                ),
                Entity(
                    model="cube",
                    position=(0, self.border_height / 2, -outer_z),
                    scale=(outer_x * 2 + 1.0, self.border_height, 1),
                    color=barrier_color,
                    collider="box",
                ),
                Entity(
                    model="cube",
                    position=(outer_x, self.border_height / 2, 0),
                    scale=(1, self.border_height, outer_z * 2 + 1.0),
                    color=barrier_color,
                    collider="box",
                ),
                Entity(
                    model="cube",
                    position=(-outer_x, self.border_height / 2, 0),
                    scale=(1, self.border_height, outer_z * 2 + 1.0),
                    color=barrier_color,
                    collider="box",
                ),
            ]
        )

        # Inner barrier walls.
        self.barriers.extend(
            [
                Entity(
                    model="cube",
                    position=(0, self.border_height / 2, inner_z),
                    scale=(inner_x * 2, self.border_height, 1),
                    color=barrier_color,
                    collider="box",
                ),
                Entity(
                    model="cube",
                    position=(0, self.border_height / 2, -inner_z),
                    scale=(inner_x * 2, self.border_height, 1),
                    color=barrier_color,
                    collider="box",
                ),
                Entity(
                    model="cube",
                    position=(inner_x, self.border_height / 2, 0),
                    scale=(1, self.border_height, inner_z * 2),
                    color=barrier_color,
                    collider="box",
                ),
                Entity(
                    model="cube",
                    position=(-inner_x, self.border_height / 2, 0),
                    scale=(1, self.border_height, inner_z * 2),
                    color=barrier_color,
                    collider="box",
                ),
            ]
        )

        # Start/finish stripe near top straight.
        Entity(
            model="cube",
            position=(0, 0.08, outer_z - 3.0),
            scale=(8, 0.02, 0.6),
            color=color.white,
        )

    def classify_position(self, point: Vec3) -> str:
        """Classify world position relative to track ring.

        Returns:
            "on_track" when inside drivable ring.
            "outside" when beyond outer boundary.
            "inner" when inside forbidden interior hole.
        """
        abs_x = abs(point.x)
        abs_z = abs(point.z)

        if abs_x > self.outer_half_extent_x or abs_z > self.outer_half_extent_z:
            return "outside"

        if abs_x < self.inner_half_extent_x and abs_z < self.inner_half_extent_z:
            return "inner"

        return "on_track"


class PlayerCar(Entity):
    """Player-controlled racing car with simple arcade physics."""

    def __init__(self, track: RaceTrack, config: CarConfig | None = None) -> None:
        super().__init__(
            model="cube",
            position=(0, 0.65, track.outer_half_extent_z - 3.8),
            scale=(1.2, 0.6, 2.3),
            color=color.azure,
            collider="box",
        )
        self.track = track
        self.config = config or CarConfig()

        self.speed = 0.0
        self.prev_position = Vec3(self.position)
        self.steer_lerp = 0.0

        # Simple visual cabin detail.
        Entity(
            parent=self,
            model="cube",
            position=(0, 0.45, -0.05),
            scale=(0.8, 0.45, 1.1),
            color=color.rgb(25, 25, 35),
        )

    def update(self) -> None:
        """Handle per-frame movement and collision response."""
        dt = time.dt
        self.prev_position = Vec3(self.position)

        # --- Throttle / braking ---
        forward_input = held_keys["w"] or held_keys["up arrow"]
        reverse_input = held_keys["s"] or held_keys["down arrow"]

        if forward_input:
            self.speed += self.config.acceleration * dt
        elif reverse_input:
            if self.speed > 0:
                self.speed -= self.config.brake_acceleration * dt
            else:
                self.speed -= self.config.reverse_acceleration * dt
        else:
            # Apply friction to gradually bring speed to zero.
            if self.speed > 0:
                self.speed = max(0.0, self.speed - self.config.friction * dt)
            elif self.speed < 0:
                self.speed = min(0.0, self.speed + self.config.friction * dt)

        self.speed = clamp(
            self.speed,
            -self.config.max_reverse_speed,
            self.config.max_forward_speed,
        )

        # --- Steering ---
        steer_input = (held_keys["d"] or held_keys["right arrow"]) - (
            held_keys["a"] or held_keys["left arrow"]
        )
        # Smooth steering response feels less jittery.
        self.steer_lerp += (steer_input - self.steer_lerp) * min(1.0, dt * 10)

        speed_factor = clamp(abs(self.speed) / self.config.max_forward_speed, 0.15, 1.0)
        turn_amount = (
            self.steer_lerp
            * self.config.steering_power
            * speed_factor
            * dt
            * (1 if self.speed >= 0 else -1)
        )
        self.rotation_y += turn_amount

        # --- Position integration ---
        self.position += self.forward * (self.speed * dt)

        # Keep car above road visually.
        self.y = 0.65

        # --- Border collision / bounce ---
        zone = self.track.classify_position(self.position)
        if zone != "on_track":
            # Move back to previous valid position.
            self.position = Vec3(self.prev_position)

            # Reverse and dampen speed to create a bounce feel.
            self.speed = -self.speed * 0.35

            # Add slight yaw change so impacts feel less rigid.
            self.rotation_y += 20 * (-1 if self.steer_lerp >= 0 else 1)


class RacingGame:
    """Coordinates entities, camera, UI, and race state."""

    def __init__(self) -> None:
        self.app = Ursina()
        window.title = "Ursina 3D Racing"
        window.borderless = False
        window.color = color.rgb(145, 205, 255)
        window.fps_counter.enabled = True

        self.track = RaceTrack()
        self.car = PlayerCar(self.track)

        self.camera_distance = 8.5
        self.camera_height = 4.0

        self.lap_count = 0
        self.max_laps = 3
        self.current_lap_time = 0.0
        self.best_lap_time: float | None = None

        self.start_line_z = self.track.outer_half_extent_z - 3.0
        self._was_before_start_line = self.car.z < self.start_line_z

        self.lap_text = Text(
            text=f"Lap: {self.lap_count}/{self.max_laps}",
            x=-0.86,
            y=0.44,
            scale=1.2,
            color=color.white,
        )
        self.timer_text = Text(
            text="Time: 0.00s",
            x=-0.86,
            y=0.38,
            scale=1.2,
            color=color.white,
        )
        self.best_text = Text(
            text="Best: --",
            x=-0.86,
            y=0.32,
            scale=1.1,
            color=color.white,
        )

        # Register update callback with Ursina.
        self.app.update = self.update

    def _update_camera(self) -> None:
        """Third-person camera that follows behind the car."""
        # Desired camera target behind car in local car-space.
        back_offset = -self.car.forward * self.camera_distance
        target_position = self.car.position + back_offset + Vec3(0, self.camera_height, 0)

        # Smoothly interpolate for a less abrupt camera motion.
        camera.position = camera.position.lerp(target_position, min(1.0, time.dt * 7.5))
        camera.look_at(self.car.position + Vec3(0, 0.9, 0))

    def _update_laps(self) -> None:
        """Increment laps when crossing the start line in forward direction."""
        self.current_lap_time += time.dt

        is_before_start_line = self.car.z < self.start_line_z

        crossed_line_forward = (
            self._was_before_start_line
            and not is_before_start_line
            and abs(self.car.x) < 4.0
            and self.car.speed > 1.5
        )

        if crossed_line_forward:
            self.lap_count += 1

            if self.lap_count > 0:
                if self.best_lap_time is None or self.current_lap_time < self.best_lap_time:
                    self.best_lap_time = self.current_lap_time
                self.current_lap_time = 0.0

            # Stop car after final lap to indicate race complete.
            if self.lap_count >= self.max_laps:
                self.car.speed = 0.0

        self._was_before_start_line = is_before_start_line

    def _update_ui(self) -> None:
        """Refresh lap and timer labels."""
        self.lap_text.text = f"Lap: {min(self.lap_count, self.max_laps)}/{self.max_laps}"

        if self.lap_count >= self.max_laps:
            self.timer_text.text = "Finished!"
        else:
            self.timer_text.text = f"Time: {self.current_lap_time:0.2f}s"

        if self.best_lap_time is None:
            self.best_text.text = "Best: --"
        else:
            self.best_text.text = f"Best: {self.best_lap_time:0.2f}s"

    def update(self) -> None:
        """Main frame update."""
        # Only let player drive while race is active.
        if self.lap_count < self.max_laps:
            self.car.update()

        self._update_camera()

        if self.lap_count < self.max_laps:
            self._update_laps()

        self._update_ui()

    def run(self) -> None:
        """Start Ursina event loop."""
        self.app.run()


if __name__ == "__main__":
    RacingGame().run()
