"""SoulSync - 时间感知深化系统（TPD）包

v2.19 新增三大子系统：
- environment  : 季节天气联动（节气/月相/天气获取/环境→心情映射/叙事注入）
- countdown    : 倒计时事件系统（Phase B）
- timeskip     : 时间跳跃叙事（Phase C）

本包为纯 Python 实现，零第三方依赖（API 天气获取用 urllib 标准库）。
"""

from .season_handler import (
    MOON_PHASES,
    SOLAR_TERM_NAMES,
    moon_phase,
    moon_phase_index,
    season_of,
    solar_term_of,
    solar_term_date,
)
from .mood_mapper import (
    EMOTION_DIMS,
    combine_mood,
    temperature_band,
    mood_deltas,
)
from .env_injector import build_environment_info, build_mood_tendency_text
from .weather_provider import WeatherProvider, CANONICAL_WEATHERS
from .countdown_calculator import (
    CountdownCalculator,
    CountdownEvent,
    KIND_WEIGHTS,
    MENTIONABLE_DAYS,
)
from .countdown_narrator import (
    KIND_ICONS,
    STAGE_META,
    day_label,
    stage_hint,
    stage_of,
)
from .countdown_injector import build_countdown_info
from .tpd_orchestrator import TPDOrchestrator, ENV_CONFIG_DEFAULTS

__all__ = [
    "MOON_PHASES",
    "SOLAR_TERM_NAMES",
    "moon_phase",
    "moon_phase_index",
    "season_of",
    "solar_term_of",
    "solar_term_date",
    "EMOTION_DIMS",
    "combine_mood",
    "temperature_band",
    "mood_deltas",
    "build_environment_info",
    "build_mood_tendency_text",
    "WeatherProvider",
    "CANONICAL_WEATHERS",
    "CountdownCalculator",
    "CountdownEvent",
    "KIND_WEIGHTS",
    "MENTIONABLE_DAYS",
    "KIND_ICONS",
    "STAGE_META",
    "day_label",
    "stage_hint",
    "stage_of",
    "build_countdown_info",
    "TPDOrchestrator",
    "ENV_CONFIG_DEFAULTS",
]
