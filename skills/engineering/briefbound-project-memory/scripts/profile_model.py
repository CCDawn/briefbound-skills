from __future__ import annotations


PROJECT_TYPE_CHOICES = ("general", "frontend", "backend", "automation", "research")
VISUAL_MODE_CHOICES = ("briefing", "console", "studio", "lab")
DENSITY_CHOICES = ("comfortable", "balanced", "compact")
SECTION_LAYOUT_CHOICES = ("standard", "narrow", "wide", "full")
DASHBOARD_PRESET_CHOICES = ("default", "ops-heavy", "review-heavy", "research-log")


SECTION_KEYS = (
    "summary",
    "collaboration",
    "lanes",
    "progress",
    "modules",
    "decisions",
    "issues",
    "todos",
    "techNotes",
    "recentUpdates",
)


SECTION_PRESETS = {
    "general": [
        "summary",
        "lanes",
        "progress",
        "modules",
        "decisions",
        "issues",
        "todos",
        "techNotes",
        "recentUpdates",
    ],
    "frontend": [
        "summary",
        "lanes",
        "progress",
        "modules",
        "issues",
        "todos",
        "decisions",
        "techNotes",
        "recentUpdates",
    ],
    "backend": [
        "summary",
        "lanes",
        "progress",
        "modules",
        "decisions",
        "issues",
        "todos",
        "techNotes",
        "recentUpdates",
    ],
    "automation": [
        "summary",
        "lanes",
        "progress",
        "issues",
        "todos",
        "modules",
        "techNotes",
        "recentUpdates",
        "decisions",
    ],
    "research": [
        "summary",
        "lanes",
        "progress",
        "techNotes",
        "issues",
        "todos",
        "decisions",
        "recentUpdates",
        "modules",
    ],
}


LABEL_PRESETS = {
    "general": {},
    "frontend": {
        "modules": "Features and Surfaces",
        "techNotes": "Implementation Notes",
    },
    "backend": {
        "modules": "Services and Modules",
        "techNotes": "Operational Notes",
    },
    "automation": {
        "modules": "Flows and Steps",
        "progress": "Automation Status",
    },
    "research": {
        "modules": "Workstreams",
        "decisions": "Research Decisions",
        "techNotes": "Evidence and Notes",
    },
}


DEFAULT_SECTION_LAYOUTS = {
    "summary": "narrow",
    "collaboration": "full",
    "progress": "wide",
    "lanes": "full",
    "techNotes": "full",
    "recentUpdates": "full",
}


PROJECT_SECTION_LAYOUTS = {
    "general": dict(DEFAULT_SECTION_LAYOUTS),
    "frontend": {
        **DEFAULT_SECTION_LAYOUTS,
        "modules": "wide",
        "issues": "wide",
    },
    "backend": {
        **DEFAULT_SECTION_LAYOUTS,
        "decisions": "wide",
        "issues": "wide",
    },
    "automation": {
        **DEFAULT_SECTION_LAYOUTS,
        "issues": "wide",
        "todos": "wide",
    },
    "research": {
        **DEFAULT_SECTION_LAYOUTS,
        "decisions": "wide",
    },
}


VISUAL_MODE_DEFAULTS = {
    "general": "briefing",
    "frontend": "studio",
    "backend": "console",
    "automation": "console",
    "research": "lab",
}


DENSITY_DEFAULTS = {
    "general": "balanced",
    "frontend": "comfortable",
    "backend": "compact",
    "automation": "compact",
    "research": "balanced",
}


PROJECT_DASHBOARD_PRESET_DEFAULTS = {
    "general": "default",
    "frontend": "review-heavy",
    "backend": "ops-heavy",
    "automation": "ops-heavy",
    "research": "research-log",
}


DASHBOARD_PRESET_LABELS = {
    "default": "Default",
    "ops-heavy": "Ops-Heavy",
    "review-heavy": "Review-Heavy",
    "research-log": "Research-Log",
}


DASHBOARD_PRESET_OVERRIDES = {
    "default": {},
    "ops-heavy": {
        "visualMode": "console",
        "density": "compact",
        "sections": [
            "summary",
            "lanes",
            "issues",
            "todos",
            "progress",
            "modules",
            "decisions",
            "techNotes",
            "recentUpdates",
        ],
        "sectionLayouts": {
            "summary": "narrow",
            "lanes": "full",
            "issues": "wide",
            "todos": "wide",
            "progress": "wide",
            "techNotes": "full",
            "recentUpdates": "full",
        },
    },
    "review-heavy": {
        "visualMode": "studio",
        "density": "comfortable",
        "sections": [
            "summary",
            "progress",
            "lanes",
            "modules",
            "issues",
            "decisions",
            "todos",
            "techNotes",
            "recentUpdates",
        ],
        "sectionLayouts": {
            "summary": "narrow",
            "progress": "wide",
            "lanes": "full",
            "modules": "wide",
            "issues": "wide",
            "techNotes": "full",
            "recentUpdates": "full",
        },
    },
    "research-log": {
        "visualMode": "lab",
        "density": "balanced",
        "sections": [
            "summary",
            "progress",
            "lanes",
            "techNotes",
            "decisions",
            "issues",
            "todos",
            "recentUpdates",
            "modules",
        ],
        "sectionLayouts": {
            "summary": "narrow",
            "progress": "wide",
            "lanes": "full",
            "techNotes": "full",
            "decisions": "wide",
            "recentUpdates": "full",
        },
    },
}


def normalize_sections(value: object, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(fallback)
    seen: set[str] = set()
    normalized: list[str] = []
    for entry in value:
        section = str(entry or "").strip()
        if section in SECTION_KEYS and section not in seen:
            seen.add(section)
            normalized.append(section)
    return normalized or list(fallback)


def normalize_section_layouts(value: object, fallback: dict[str, str]) -> dict[str, str]:
    normalized = dict(fallback)
    if not isinstance(value, dict):
        return normalized
    for raw_key, raw_layout in value.items():
        section = str(raw_key or "").strip()
        layout = str(raw_layout or "").strip().lower()
        if section in SECTION_KEYS and layout in SECTION_LAYOUT_CHOICES:
            normalized[section] = layout
    return normalized


def resolve_dashboard_preset(project_type: str, dashboard_preset: str | None) -> str:
    if dashboard_preset in DASHBOARD_PRESET_CHOICES:
        return dashboard_preset
    return PROJECT_DASHBOARD_PRESET_DEFAULTS.get(project_type, "default")


def base_profile(project_type: str, dashboard_preset: str | None = None) -> dict:
    if project_type not in PROJECT_TYPE_CHOICES:
        raise ValueError(f"Unsupported project type: {project_type}")
    preset = resolve_dashboard_preset(project_type, dashboard_preset)
    base = {
        "projectType": project_type,
        "dashboardPreset": preset,
        "visualMode": VISUAL_MODE_DEFAULTS[project_type],
        "density": DENSITY_DEFAULTS[project_type],
        "sections": list(SECTION_PRESETS[project_type]),
        "sectionLayouts": dict(PROJECT_SECTION_LAYOUTS[project_type]),
        "labels": dict(LABEL_PRESETS[project_type]),
    }
    overrides = DASHBOARD_PRESET_OVERRIDES.get(preset, {})
    if overrides.get("visualMode") in VISUAL_MODE_CHOICES:
        base["visualMode"] = overrides["visualMode"]
    if overrides.get("density") in DENSITY_CHOICES:
        base["density"] = overrides["density"]
    if "sections" in overrides:
        base["sections"] = normalize_sections(overrides["sections"], base["sections"])
    if "sectionLayouts" in overrides:
        base["sectionLayouts"] = normalize_section_layouts(overrides["sectionLayouts"], base["sectionLayouts"])
    return base


def build_profile(
    project_type: str,
    *,
    dashboard_preset: str | None = None,
    visual_mode: str | None = None,
    density: str | None = None,
) -> dict:
    base = base_profile(project_type, dashboard_preset)
    profile = {
        "projectType": base["projectType"],
        "dashboardPreset": base["dashboardPreset"],
        "labels": dict(base["labels"]),
    }
    if visual_mode in VISUAL_MODE_CHOICES:
        profile["visualMode"] = visual_mode
    if density in DENSITY_CHOICES:
        profile["density"] = density
    return profile


def effective_profile(profile: dict | None) -> dict:
    source = profile or {}
    project_type = str(source.get("projectType") or "general").strip()
    if project_type not in PROJECT_TYPE_CHOICES:
        project_type = "general"
    base = base_profile(project_type, source.get("dashboardPreset"))

    resolved = {
        "projectType": base["projectType"],
        "dashboardPreset": base["dashboardPreset"],
        "visualMode": base["visualMode"],
        "density": base["density"],
        "sections": list(base["sections"]),
        "sectionLayouts": dict(base["sectionLayouts"]),
        "labels": dict(base["labels"]),
    }

    visual_mode = source.get("visualMode")
    if visual_mode in VISUAL_MODE_CHOICES:
        resolved["visualMode"] = visual_mode

    density = source.get("density")
    if density in DENSITY_CHOICES:
        resolved["density"] = density

    resolved["sections"] = normalize_sections(source.get("sections"), resolved["sections"])
    resolved["sectionLayouts"] = normalize_section_layouts(source.get("sectionLayouts"), resolved["sectionLayouts"])

    labels = source.get("labels")
    if isinstance(labels, dict):
        for key, value in labels.items():
            section = str(key or "").strip()
            if section in SECTION_KEYS and str(value or "").strip():
                resolved["labels"][section] = str(value)

    return resolved
