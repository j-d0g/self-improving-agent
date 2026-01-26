"""
Bullet-format playbook utilities for ACE knowledge files.

Bullets are trackable units with counters for measuring effectiveness:
    [ex-00001] helpful=5 harmful=1 :: Query pattern for revenue...

This module provides parsing, updating, and delta operations for these bullets.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator

# Pattern for parsing bullet lines
# Format: [id] helpful=X harmful=Y :: content
BULLET_PATTERN = re.compile(
    r'^\[([^\]]+)\]\s+helpful=(\d+)\s+harmful=(\d+)\s*::\s*(.*)$'
)

# Prefix patterns for different bullet types (section name -> ID prefix)
BULLET_PREFIXES = {
    'schema': 'sch',
    'strategies_&_insights': 'str',
    'formulas_&_calculations': 'calc',
    'code_templates': 'code',
    'edge_cases_&_pitfalls': 'edge',
    'common_mistakes': 'err',
    'query_interpretation': 'interp',
    # Legacy prefixes for backwards compatibility
    'examples': 'ex',
    'errors': 'err',
    'patterns': 'pat',
}


class Tag(Enum):
    """Tags assigned by the Reflector to bullets."""
    HELPFUL = "helpful"
    HARMFUL = "harmful"
    NEUTRAL = "neutral"


class OpType(Enum):
    """Delta operation types for Curator."""
    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class Bullet:
    """A single trackable bullet with counters."""
    id: str
    helpful: int
    harmful: int
    content: str
    # Additional lines that belong to this bullet (indented content)
    continuation: list[str] = field(default_factory=list)

    def format(self) -> str:
        """Format bullet as string with all continuation lines."""
        header = f"[{self.id}] helpful={self.helpful} harmful={self.harmful} :: {self.content}"
        if self.continuation:
            return header + '\n' + '\n'.join(self.continuation)
        return header

    def net_score(self) -> int:
        """Net effectiveness score (helpful - harmful)."""
        return self.helpful - self.harmful

    def total_uses(self) -> int:
        """Total times this bullet was referenced."""
        return self.helpful + self.harmful


@dataclass
class BulletTag:
    """A tag assigned to a bullet by the Reflector."""
    bullet_id: str
    tag: Tag
    insight: str | None = None
    query: str | None = None
    run_id: str | None = None


@dataclass
class DeltaOp:
    """A delta operation for modifying the playbook."""
    op_type: OpType
    section: str | None = None  # For ADD
    bullet_id: str | None = None  # For UPDATE/DELETE
    content: str | None = None  # For ADD/UPDATE
    reason: str | None = None  # Human-readable explanation


@dataclass
class Playbook:
    """A knowledge file in bullet format."""
    path: Path
    sections: dict[str, list[Bullet | str]] = field(default_factory=dict)
    # Non-bullet content (headers, blank lines, etc.)
    preamble: list[str] = field(default_factory=list)

    def all_bullets(self) -> Iterator[Bullet]:
        """Iterate over all bullets in the playbook."""
        for items in self.sections.values():
            for item in items:
                if isinstance(item, Bullet):
                    yield item

    def get_bullet(self, bullet_id: str) -> Bullet | None:
        """Find a bullet by ID."""
        for bullet in self.all_bullets():
            if bullet.id == bullet_id:
                return bullet
        return None

    def get_next_id(self, prefix: str) -> str:
        """Generate the next available ID for a prefix."""
        max_num = 0
        pattern = re.compile(rf'^{re.escape(prefix)}-(\d+)$')
        for bullet in self.all_bullets():
            match = pattern.match(bullet.id)
            if match:
                max_num = max(max_num, int(match.group(1)))
        return f"{prefix}-{max_num + 1:05d}"

    def format(self) -> str:
        """Format entire playbook as string."""
        lines = list(self.preamble)

        for section_name, items in self.sections.items():
            # Add section header
            lines.append(f"\n## {section_name}\n")
            for item in items:
                if isinstance(item, Bullet):
                    lines.append(item.format())
                else:
                    lines.append(item)
            lines.append("")  # Blank line after section

        return '\n'.join(lines)


def parse_bullet(line: str) -> Bullet | None:
    """Parse a single line as a bullet, or return None if not a bullet."""
    match = BULLET_PATTERN.match(line.strip())
    if match:
        return Bullet(
            id=match.group(1),
            helpful=int(match.group(2)),
            harmful=int(match.group(3)),
            content=match.group(4),
        )
    return None


def parse_playbook(content: str, path: Path | None = None) -> Playbook:
    """Parse a playbook file into structured format."""
    playbook = Playbook(path=path or Path("unknown"))
    lines = content.split('\n')

    current_section: str | None = None
    current_bullet: Bullet | None = None
    in_preamble = True

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check for section header
        if stripped.startswith('## '):
            in_preamble = False
            # Save any pending bullet
            if current_bullet and current_section:
                playbook.sections[current_section].append(current_bullet)
                current_bullet = None

            current_section = stripped[3:].strip()
            if current_section not in playbook.sections:
                playbook.sections[current_section] = []
            i += 1
            continue

        # If still in preamble, collect it
        if in_preamble:
            playbook.preamble.append(line)
            i += 1
            continue

        # Try to parse as bullet
        bullet = parse_bullet(line)
        if bullet:
            # Save previous bullet if any
            if current_bullet and current_section:
                playbook.sections[current_section].append(current_bullet)
            current_bullet = bullet
            i += 1
            continue

        # Check if this is a continuation line (indented, follows a bullet)
        if current_bullet and line.startswith('  ') and stripped:
            current_bullet.continuation.append(line)
            i += 1
            continue

        # Non-bullet content in section
        if current_section:
            # Save pending bullet first
            if current_bullet:
                playbook.sections[current_section].append(current_bullet)
                current_bullet = None
            # Only add non-empty lines or significant whitespace
            if stripped or (lines[i-1:i] and not lines[i-1].strip()):
                playbook.sections[current_section].append(line)

        i += 1

    # Don't forget the last bullet
    if current_bullet and current_section:
        playbook.sections[current_section].append(current_bullet)

    return playbook


def update_counters(playbook: Playbook, tags: list[BulletTag]) -> list[str]:
    """
    Apply tag increments to playbook bullets.

    Multiple tags for the same bullet are accumulated (e.g., 2 HELPFUL tags = +2).

    Returns list of bullet IDs that were updated.
    """
    # Accumulate tag counts per bullet
    tag_counts: dict[str, dict[str, int]] = {}
    for t in tags:
        if t.bullet_id not in tag_counts:
            tag_counts[t.bullet_id] = {'helpful': 0, 'harmful': 0}
        if t.tag == Tag.HELPFUL:
            tag_counts[t.bullet_id]['helpful'] += 1
        elif t.tag == Tag.HARMFUL:
            tag_counts[t.bullet_id]['harmful'] += 1

    updated = []
    for bullet in playbook.all_bullets():
        if bullet.id in tag_counts:
            bullet.helpful += tag_counts[bullet.id]['helpful']
            bullet.harmful += tag_counts[bullet.id]['harmful']
            updated.append(bullet.id)

    return updated


def apply_operation(playbook: Playbook, op: DeltaOp) -> bool:
    """
    Apply a single delta operation to the playbook.

    Returns True if the operation was applied successfully.
    """
    if op.op_type == OpType.DELETE and op.bullet_id:
        # Find and remove the bullet
        for section_items in playbook.sections.values():
            for i, item in enumerate(section_items):
                if isinstance(item, Bullet) and item.id == op.bullet_id:
                    section_items.pop(i)
                    return True
        return False

    elif op.op_type == OpType.UPDATE and op.bullet_id and op.content:
        # Find and update the bullet content
        bullet = playbook.get_bullet(op.bullet_id)
        if bullet:
            bullet.content = op.content
            # Clear continuation if content completely replaced
            bullet.continuation = []
            return True
        return False

    elif op.op_type == OpType.ADD and op.section and op.content:
        # Add new bullet to section
        if op.section not in playbook.sections:
            playbook.sections[op.section] = []

        # Determine prefix from section name
        section_lower = op.section.lower().replace(' ', '_')
        prefix = BULLET_PREFIXES.get(section_lower, 'item')
        new_id = playbook.get_next_id(prefix)

        new_bullet = Bullet(
            id=new_id,
            helpful=0,
            harmful=0,
            content=op.content,
        )
        playbook.sections[op.section].append(new_bullet)
        return True

    return False


def apply_operations(playbook: Playbook, ops: list[DeltaOp]) -> tuple[int, int]:
    """
    Apply multiple delta operations to the playbook.

    Returns (successful_count, failed_count).
    """
    success = 0
    failed = 0
    for op in ops:
        if apply_operation(playbook, op):
            success += 1
        else:
            failed += 1
    return success, failed


def load_playbook(path: Path) -> Playbook:
    """Load a playbook from a file."""
    content = path.read_text()
    return parse_playbook(content, path)


def save_playbook(playbook: Playbook) -> None:
    """Save a playbook to its file."""
    if playbook.path:
        playbook.path.write_text(playbook.format())


def get_playbook_stats(playbook: Playbook) -> dict:
    """Get statistics about a playbook's bullets."""
    bullets = list(playbook.all_bullets())

    if not bullets:
        return {
            'total_bullets': 0,
            'total_helpful': 0,
            'total_harmful': 0,
            'avg_net_score': 0.0,
            'sections': {},
        }

    total_helpful = sum(b.helpful for b in bullets)
    total_harmful = sum(b.harmful for b in bullets)

    section_stats = {}
    for section_name, items in playbook.sections.items():
        section_bullets = [i for i in items if isinstance(i, Bullet)]
        if section_bullets:
            section_stats[section_name] = {
                'count': len(section_bullets),
                'helpful': sum(b.helpful for b in section_bullets),
                'harmful': sum(b.harmful for b in section_bullets),
            }

    return {
        'total_bullets': len(bullets),
        'total_helpful': total_helpful,
        'total_harmful': total_harmful,
        'avg_net_score': (total_helpful - total_harmful) / len(bullets),
        'sections': section_stats,
    }
