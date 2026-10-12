"""The layout engine: suggests where each item should go (readme section 5).

How it works:
1. Every item gets a target spot from a rule for its kind. For example, the
   keyboard goes front and center, and the mouse goes beside the keyboard
   on the side of the user's dominant hand. Items without a rule are pulled
   toward the user; the more often an item is used, the harder it is pulled.
2. A layout is scored: the distance of every item from its target, times
   how much that item matters, plus big penalties for items that overlap
   or that crowd the space right in front of the user. Lower is better.
3. Items are first placed one at a time, most important first, each in
   its best free spot. Then simulated annealing searches for a lower score. It makes thousands of
   small random changes (move, swap, turn, or take an item off the desk).
   Changes that help are kept. Early on, some changes that hurt are kept
   too, so the search can escape a layout that is only good locally.
4. Every item gets a plain-language reason for where it ended up.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from cleanmydesk.model.project import Desk, Item, WorkProfile

USAGE_WEIGHT = {"rarely": 0.3, "sometimes": 1.0, "often": 2.5, "constantly": 5.0}
USAGE_PHRASE = {"rarely": "rarely", "sometimes": "sometimes", "often": "often", "constantly": "all the time"}

GAP_CM = 1.0  # space kept between items
EASY_REACH_CM = 35.0  # readme section 3.3, zone 1
ARM_REACH_CM = 60.0  # zone 2; beyond this is the stretch zone
WORK_ZONE_CM = 25.0  # space in front of the user kept for hands
OVERLAP_PENALTY = 50.0  # per square cm of overlap
WORK_ZONE_PENALTY = 0.5  # per square cm of clutter in the work zone
DEFAULT_KEYBOARD_WIDTH_CM = 44.0
HAND_TOOLS = ("keyboard", "mouse", "notebook")  # allowed in the work zone
NEVER_TURNED = ("screen", "keyboard", "mouse")  # these only work facing the user
# How far from the front edge an item without a rule is pulled, by usage.
OTHER_ITEM_DISTANCE_CM = {"sometimes": 35.0, "often": 22.0, "constantly": 15.0}


@dataclass
class Placement:
    item_id: str
    x_cm: float  # left edge, measured from the left side of the desk
    y_cm: float  # back edge, measured from the back of the desk
    width_cm: float  # as placed (width and depth swap when turned)
    depth_cm: float
    rotated: bool


@dataclass
class LayoutResult:
    placements: list[Placement]
    off_desk: list[Item]  # items to put in a drawer or on a shelf
    reasons: dict[str, str]  # item id -> why it is where it is


@dataclass
class _Target:
    x: float
    y: float
    weight: float
    rule: str


def suggest_layout(desk: Desk, items: list[Item], profile: WorkProfile, seed: int = 0) -> LayoutResult:
    if not items:
        return LayoutResult([], [], {})
    search = _Search(desk, items, profile, random.Random(seed))
    search.run()
    return search.result()


class _Search:
    def __init__(self, desk: Desk, items: list[Item], profile: WorkProfile, rng: random.Random) -> None:
        self.desk = desk
        self.items = items
        self.profile = profile
        self.rng = rng
        self.side = -1 if profile.handedness == "left" else 1
        keyboards = [item.width_cm for item in items if item.kind == "keyboard"]
        self.keyboard_width = keyboards[0] if keyboards else DEFAULT_KEYBOARD_WIDTH_CM
        self.targets = [self._target(item) for item in items]
        self.off_desk_cost = math.hypot(desk.width_cm, desk.depth_cm) + 30

        # Current state, one entry per item: on the desk?, center, turned?
        n = len(items)
        self.on = [False] * n
        self.cx = [0.0] * n
        self.cy = [0.0] * n
        self.rot = [False] * n

        # Starting layout: the most important items pick their spots first.
        for i in sorted(range(n), key=lambda k: -self.targets[k].weight):
            self._place_in_free_spot(i, grid_step=3.0)

    # Sizes and fitting

    def size(self, i: int, rotated: bool | None = None) -> tuple[float, float]:
        item = self.items[i]
        turned = self.rot[i] if rotated is None else rotated
        return (item.depth_cm, item.width_cm) if turned else (item.width_cm, item.depth_cm)

    def fits(self, i: int, rotated: bool) -> bool:
        if rotated and self.items[i].kind in NEVER_TURNED:
            return False
        w, d = self.size(i, rotated)
        return w <= self.desk.width_cm and d <= self.desk.depth_cm

    def clamp(self, i: int, x: float, y: float) -> tuple[float, float]:
        w, d = self.size(i)
        x = min(max(x, w / 2), self.desk.width_cm - w / 2)
        y = min(max(y, d / 2), self.desk.depth_cm - d / 2)
        return x, y

    # Targets (step 1)

    def _target(self, item: Item) -> _Target:
        W, D = self.desk.width_cm, self.desk.depth_cm
        s = self.side
        mid = W / 2
        kw = self.keyboard_width
        w, d = item.width_cm, item.depth_cm
        u = USAGE_WEIGHT.get(item.usage, 1.0)
        writing = "writing" in self.profile.tasks or "drawing" in self.profile.tasks

        if item.kind == "screen":
            x, y, weight = mid, d / 2 + max(0.0, D - d - 55), 4 * u
        elif item.kind == "keyboard":
            x, y, weight = mid, D - d / 2 - 5, 4 * u
        elif item.kind == "mouse":
            x, y, weight = mid + s * (kw / 2 + 8 + w / 2), D - d / 2 - 8, 3 * u
        elif item.kind == "notebook" and writing:
            x, y, weight = mid + s * (kw / 2 + w / 2 + 22), D - d / 2 - 3, 2 * u
        elif item.kind == "notebook":
            x, y, weight = mid - s * (kw / 2 + w / 2 + 10), D - d / 2 - 10, u
        elif item.kind == "drink":
            x, y, weight = mid + s * (kw / 2 + w / 2 + 30), D - d / 2 - 15, 1.5 * u
        elif item.kind == "phone":
            x, y, weight = mid - s * (kw / 2 + w / 2 + 12), D - d / 2 - 12, 1.5 * u
        elif item.kind == "lamp":
            # Opposite the writing hand, so the hand does not shade the work.
            x, y, weight = (w / 2 if s > 0 else W - w / 2), d / 2, 2 * max(u, 1.0)
        elif item.usage == "rarely":
            # Back corner on the side of the dominant hand, out of the way.
            x, y, weight = (W - w / 2 if s > 0 else w / 2), d / 2, u
        else:
            x, y, weight = mid, D - d / 2 - OTHER_ITEM_DISTANCE_CM.get(item.usage, 35.0), u
        rule = item.kind if item.kind != "notebook" else ("notebook_writing" if writing else "notebook")
        x = min(max(x, w / 2), W - w / 2) if w <= W else W / 2
        y = min(max(y, d / 2), D - d / 2) if d <= D else D / 2
        return _Target(x, y, weight, rule)

    # Score (step 2)

    def unary(self, i: int) -> float:
        target = self.targets[i]
        if not self.on[i]:
            return target.weight * self.off_desk_cost
        cost = target.weight * math.hypot(self.cx[i] - target.x, self.cy[i] - target.y)
        if self.items[i].kind not in HAND_TOOLS:
            w, d = self.size(i)
            mid, D = self.desk.width_cm / 2, self.desk.depth_cm
            ox = _overlap_1d(self.cx[i] - w / 2, self.cx[i] + w / 2, mid - WORK_ZONE_CM, mid + WORK_ZONE_CM)
            oy = _overlap_1d(self.cy[i] - d / 2, self.cy[i] + d / 2, D - WORK_ZONE_CM, D)
            # Capped, so keeping this space clear never outweighs keeping
            # the item on the desk at all.
            cost += min(WORK_ZONE_PENALTY * ox * oy, 0.5 * target.weight * self.off_desk_cost)
        return cost

    def overlap(self, i: int, j: int, gap: float = GAP_CM) -> float:
        """Overlap area of two items, counting the gap kept between items."""
        if not (self.on[i] and self.on[j]):
            return 0.0
        wi, di = self.size(i)
        wj, dj = self.size(j)
        # Two boxes overlap by (sum of half sizes) - (distance between centers).
        ox = (wi + wj) / 2 + gap - abs(self.cx[i] - self.cx[j])
        if ox <= 0:
            return 0.0
        oy = (di + dj) / 2 + gap - abs(self.cy[i] - self.cy[j])
        if oy <= 0:
            return 0.0
        return min(ox, wi + gap, wj + gap) * min(oy, di + gap, dj + gap)

    def local_cost(self, changed: tuple[int, ...]) -> float:
        """The part of the score that depends on the changed items."""
        cost = sum(self.unary(i) for i in changed)
        for i in changed:
            for j in range(len(self.items)):
                if j != i and (j not in changed or j > i):
                    cost += OVERLAP_PENALTY * self.overlap(i, j)
        return cost

    def total_cost(self) -> float:
        n = len(self.items)
        cost = sum(self.unary(i) for i in range(n))
        for i in range(n):
            for j in range(i + 1, n):
                cost += OVERLAP_PENALTY * self.overlap(i, j)
        return cost

    # Search (step 3)

    def run(self) -> None:
        n = len(self.items)
        steps = min(8000, 1500 + 300 * n)
        start_temp, end_temp = 30.0, 0.05
        best_cost = self.total_cost()
        best = self._snapshot()
        cost = best_cost
        for step in range(steps):
            temp = start_temp * (end_temp / start_temp) ** (step / steps)
            move = self._random_move()
            if move is None:
                continue
            changed, apply = move
            saved = [(i, self.on[i], self.cx[i], self.cy[i], self.rot[i]) for i in changed]
            before = self.local_cost(changed)
            apply()
            delta = self.local_cost(changed) - before
            if delta <= 0 or self.rng.random() < math.exp(-delta / temp):
                cost += delta
                if cost < best_cost - 1e-9:
                    best_cost, best = cost, self._snapshot()
            else:
                for i, on, x, y, rot in saved:
                    self.on[i], self.cx[i], self.cy[i], self.rot[i] = on, x, y, rot
        self._restore(best)
        self._fix_overlaps()
        self._bring_back_items()

    def _random_move(self):
        n = len(self.items)
        rng = self.rng
        i = rng.randrange(n)
        kind = rng.random()
        if not self.on[i]:
            if kind < 0.3 and any(self.fits(i, r) for r in (False, True)):
                return (i,), lambda: self._put_on(i)
            return None
        if kind < 0.55:
            step = 2 + 15 * rng.random()
            x = self.cx[i] + rng.uniform(-step, step)
            y = self.cy[i] + rng.uniform(-step, step)
            return (i,), lambda: self._move(i, x, y)
        if kind < 0.65:
            return (i,), lambda: self._put_on(i)
        if kind < 0.82:
            j = rng.randrange(n)
            if j == i or not self.on[j]:
                return None
            return (i, j), lambda: self._swap(i, j)
        if kind < 0.95:
            if not self.fits(i, not self.rot[i]):
                return None
            return (i,), lambda: self._turn(i)
        return (i,), lambda: self._take_off(i)

    def _move(self, i: int, x: float, y: float) -> None:
        self.cx[i], self.cy[i] = self.clamp(i, x, y)

    def _put_on(self, i: int) -> None:
        choices = [r for r in (False, True) if self.fits(i, r)]
        self.on[i] = True
        self.rot[i] = self.rng.choice(choices)
        w, d = self.size(i)
        self._move(i, self.rng.uniform(w / 2, self.desk.width_cm - w / 2),
                   self.rng.uniform(d / 2, self.desk.depth_cm - d / 2))

    def _swap(self, i: int, j: int) -> None:
        (xi, yi), (xj, yj) = (self.cx[i], self.cy[i]), (self.cx[j], self.cy[j])
        self._move(i, xj, yj)
        self._move(j, xi, yi)

    def _turn(self, i: int) -> None:
        self.rot[i] = not self.rot[i]
        self._move(i, self.cx[i], self.cy[i])

    def _take_off(self, i: int) -> None:
        self.on[i] = False

    def _snapshot(self):
        return (list(self.on), list(self.cx), list(self.cy), list(self.rot))

    def _restore(self, snapshot) -> None:
        self.on, self.cx, self.cy, self.rot = (list(part) for part in snapshot)

    def _fix_overlaps(self) -> None:
        """Make sure no two items overlap, moving the less important one."""
        n = len(self.items)
        while True:
            pair = next(
                ((i, j) for i in range(n) for j in range(i + 1, n) if self.overlap(i, j, gap=0) > 0.01),
                None,
            )
            if pair is None:
                return
            i, j = pair
            loser = i if self.targets[i].weight < self.targets[j].weight else j
            if not self._place_in_free_spot(loser):
                self.on[loser] = False

    def _bring_back_items(self) -> None:
        """Put items back on the desk if a free spot opened up."""
        off = [i for i in range(len(self.items)) if not self.on[i]]
        for i in sorted(off, key=lambda k: -self.targets[k].weight):
            self._place_in_free_spot(i)

    def _place_in_free_spot(self, i: int, grid_step: float = 2.0) -> bool:
        """Move item i to the best spot where it overlaps nothing."""
        saved = (self.on[i], self.cx[i], self.cy[i], self.rot[i])
        self.on[i] = True
        # Score every spot on a grid, then take the cheapest one that is free.
        candidates = []
        for rotated in (False, True):
            if not self.fits(i, rotated):
                continue
            self.rot[i] = rotated
            w, d = self.size(i)
            for x in _grid(w / 2, self.desk.width_cm - w / 2, grid_step):
                for y in _grid(d / 2, self.desk.depth_cm - d / 2, grid_step):
                    self.cx[i], self.cy[i] = x, y
                    candidates.append((self.unary(i), x, y, rotated))
        candidates.sort()
        others = [j for j in range(len(self.items)) if j != i and self.on[j]]
        for _cost, x, y, rotated in candidates:
            self.cx[i], self.cy[i], self.rot[i] = x, y, rotated
            if not any(self.overlap(i, j) > 0 for j in others):
                return True
        self.on[i], self.cx[i], self.cy[i], self.rot[i] = saved
        return False

    # Result and reasons (step 4)

    def result(self) -> LayoutResult:
        placements, off_desk, reasons = [], [], {}
        for i, item in enumerate(self.items):
            if self.on[i]:
                w, d = self.size(i)
                placements.append(Placement(item.id, self.cx[i] - w / 2, self.cy[i] - d / 2, w, d, self.rot[i]))
            else:
                off_desk.append(item)
            reasons[item.id] = self._reason(i)
        return LayoutResult(placements, off_desk, reasons)

    def _reason(self, i: int) -> str:
        item = self.items[i]
        usage = USAGE_PHRASE.get(item.usage, "sometimes")
        if not self.on[i]:
            if self.fits(i, False) or self.fits(i, True):
                return (f"Put it in a drawer or on a shelf. There isn't room for everything, "
                        f"and you use it {usage}, so it gives up its spot first.")
            return "Put it in a drawer or on a shelf. It is too big for this desk."

        target = self.targets[i]
        near = math.hypot(self.cx[i] - target.x, self.cy[i] - target.y) < 15
        either = self.profile.handedness == "either"
        hand = "right" if self.side > 0 else "left"
        other = "left" if self.side > 0 else "right"
        rules = {
            "screen": "Centered at the back, so you look straight ahead at it from a comfortable distance.",
            "keyboard": "Front and center, where your hands rest when you type.",
            "mouse": ("Right next to the keyboard." if either else
                      f"Right next to the keyboard on your {hand} side, for your {hand} hand."),
            "notebook_writing": ("At the front, ready for writing." if either else
                                 f"At the front on your {hand} side, ready for writing."),
            "notebook": "Beside the keyboard, out of the way but easy to grab.",
            "drink": ("Within easy reach but away from the keyboard, so spills miss it." if either else
                      f"On your {hand} side, easy to reach but away from the keyboard so spills miss it."),
            "phone": ("Within easy reach, beside the keyboard." if either else
                      f"On your {other} side, so you can pick it up without letting go of the mouse."),
            "lamp": ("In a back corner, out of the way." if either else
                     f"In the back {other} corner, opposite your writing hand, so your hand "
                     "doesn't cast a shadow on your work."),
        }
        if near and target.rule in rules:
            return rules[target.rule]

        zone = self._zone(i)
        where = self._position_words(i)
        if zone == "easy":
            text = f"{where}, close to you"
            if item.usage in ("often", "constantly"):
                text += f", because you use it {usage}"
            elif item.usage == "rarely":
                text += ", in a gap nothing else needed"
        elif zone == "arm":
            text = f"{where}, within arm's reach"
            if item.usage == "rarely":
                text += ", in a gap nothing else needed"
        else:
            text = f"{where}, toward the edge of the desk"
            if item.usage == "rarely":
                text += ", since you rarely use it"
            elif item.usage in ("often", "constantly"):
                text += ", because the closer spots are taken"
        return text + "."

    def _zone(self, i: int) -> str:
        w, d = self.size(i)
        seat_x, seat_y = self.desk.width_cm / 2, self.desk.depth_cm
        nearest_x = min(max(seat_x, self.cx[i] - w / 2), self.cx[i] + w / 2)
        nearest_y = min(max(seat_y, self.cy[i] - d / 2), self.cy[i] + d / 2)
        distance = math.hypot(nearest_x - seat_x, nearest_y - seat_y)
        if distance <= EASY_REACH_CM:
            return "easy"
        return "arm" if distance <= ARM_REACH_CM else "stretch"

    def _position_words(self, i: int) -> str:
        W, D = self.desk.width_cm, self.desk.depth_cm
        across = "left" if self.cx[i] < W / 3 else "right" if self.cx[i] > 2 * W / 3 else ""
        depth = "back" if self.cy[i] < D / 3 else "front" if self.cy[i] > 2 * D / 3 else ""
        if across and depth:
            return f"At the {depth} {across}"
        if across or depth:
            return f"At the {across or depth}"
        return "In the middle of the desk"


def zone_of(desk: Desk, placement: Placement) -> str:
    """Which reach zone a placed item is in: "easy", "arm" or "stretch"."""
    seat_x, seat_y = desk.width_cm / 2, desk.depth_cm
    nearest_x = min(max(seat_x, placement.x_cm), placement.x_cm + placement.width_cm)
    nearest_y = min(max(seat_y, placement.y_cm), placement.y_cm + placement.depth_cm)
    distance = math.hypot(nearest_x - seat_x, nearest_y - seat_y)
    if distance <= EASY_REACH_CM:
        return "easy"
    return "arm" if distance <= ARM_REACH_CM else "stretch"


def _overlap_1d(a1: float, a2: float, b1: float, b2: float) -> float:
    return max(0.0, min(a2, b2) - max(a1, b1))


def _grid(low: float, high: float, step: float = 2.0):
    if high <= low:
        yield low
        return
    count = int((high - low) // step)
    for k in range(count + 1):
        yield low + k * step
    if low + count * step < high:
        yield high
