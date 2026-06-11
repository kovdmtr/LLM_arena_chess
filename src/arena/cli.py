"""Консольный интерфейс ``arena``: прогон партии и турнира из терминала.

Команды:

- ``arena models`` — показать каталог моделей и наличие ключа для каждой;
- ``arena play WHITE BLACK`` — сыграть одну партию между двумя моделями;
- ``arena tournament M1 M2 [M3 …] [--double]`` — round-robin турнир.

CLI — тонкая обёртка над уже готовыми слоями (``GameRunner``/``TournamentRunner`` +
``storage`` + ★ ``engine``/``analysis``); веб-слой он не трогает. Артефакты партий
кладутся в ``output.games_dir`` (как в вебе), итог турнира — в
``<games_dir>/tournaments/<id>/``. Построение игроков и движка вынесено в параметры
(швы для тестов: фейковые игроки без сети, движок отключаемый).
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from arena.analysis import ClassificationThresholds, analyze_game
from arena.arena import GameRunner, ModelPlayer, new_game_record
from arena.config import ConfigError, ModelCatalog, ResolvedModel, Settings
from arena.config.settings import DEFAULT_CONFIG_PATH, DEFAULT_ENV_FILE
from arena.engine import EngineUnavailableError, build_engine
from arena.models import GameRecord, PlayerInfo, Side
from arena.providers import ProviderError, create_provider
from arena.stats import StatsTable
from arena.storage import export_pgn, export_report, game_dir, save_game
from arena.tournament import (
    TournamentRunner,
    export_tournament,
    new_tournament_record,
)

_SIDES: tuple[Side, Side] = ("white", "black")

# Швы (для тестов подменяются фейками без сети/движка).
PlayerFactory = Callable[[Side, ResolvedModel], object]
TournamentPlayerFactory = Callable[[Side, PlayerInfo], object]
EngineFactory = Callable[[], object | None]
Clock = Callable[[], datetime]
Writer = Callable[[str], None]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _configure_output_encoding() -> None:
    """Перевести stdout/stderr на UTF-8, чтобы кириллица/символы не падали на Windows.

    Консоль Windows по умолчанию ``cp1252``/``cp866`` — печать кириллицы и значков
    (``✓``/``★``) роняет процесс ``UnicodeEncodeError``. ``reconfigure`` доступен с
    Python 3.7; ``errors="replace"`` страхует от любых неотображаемых символов.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # поток уже закрыт/подменён — не критично
                pass


def _default_player_factory(side: Side, resolved: ResolvedModel) -> ModelPlayer:
    """Реальный игрок: провайдер по резолвленной модели + ``ModelPlayer``."""
    return ModelPlayer(create_provider(resolved))


def _engine_factory_from(settings: Settings) -> EngineFactory:
    """Фабрика движка из конфига (единый путь ``build_engine``: открытый или ``None``)."""
    engine_cfg = settings.config.engine
    return lambda: build_engine(engine_cfg, depth=engine_cfg.hint_depth)


def _player_info(catalog: ModelCatalog, model_id: str) -> PlayerInfo:
    """Несекретное описание модели для записи турнира (``PlayerInfo``)."""
    model = catalog.get(model_id)
    return PlayerInfo(
        model_id=model.id, provider=model.provider, display_name=model.display_name
    )


# --- команда: список моделей ----------------------------------------------


def cmd_models(settings: Settings, *, out: Writer = print) -> int:
    """Показать каталог моделей с пометкой наличия ключа."""
    catalog = ModelCatalog.from_settings(settings)
    models = catalog.models
    if not models:
        out("Каталог моделей пуст (см. models: в config.yaml).")
        return 0
    out("Доступные модели:")
    for model in models:
        key = "✓ ключ" if catalog.has_key(model.id) else "✗ нет ключа"
        out(f"  {model.id:<24} {model.provider:<12} {model.display_name:<24} [{key}]")
    return 0


# --- команда: одна партия -------------------------------------------------


def cmd_play(
    args: argparse.Namespace,
    *,
    settings: Settings,
    player_factory: PlayerFactory = _default_player_factory,
    engine_factory: EngineFactory | None = None,
    clock: Clock = _utcnow,
    out: Writer = print,
) -> int:
    """Сыграть одну партию ``WHITE`` vs ``BLACK`` и сохранить артефакты."""
    catalog = ModelCatalog.from_settings(settings)
    try:
        resolved = {
            "white": catalog.resolve(args.white),
            "black": catalog.resolve(args.black),
        }
    except ConfigError as exc:
        out(f"Ошибка конфигурации: {exc}")
        return 2

    if engine_factory is None:
        engine_factory = _engine_factory_from(settings)

    game_id = args.id or uuid.uuid4().hex[:12]
    games_root = settings.config.output.games_dir
    try:
        record = _play_game(
            resolved,
            settings=settings,
            game_id=game_id,
            games_root=games_root,
            player_factory=player_factory,
            engine_factory=engine_factory,
            clock=clock,
            max_plies=args.max_plies,
            persist=not args.no_persist,
        )
    except ProviderError as exc:
        out(f"Сбой провайдера: {exc}")
        return 1

    white = record.players["white"]
    black = record.players["black"]
    out(f"Партия {record.id}: {white.display_name} (белые) vs {black.display_name} (чёрные)")
    out(f"Результат: {record.result} ({record.termination or '—'}); ходов: {len(record.moves)}")
    if record.analysis is not None:
        out("★ Пост-анализ выполнен (см. report.html).")
    if not args.no_persist:
        out(f"Артефакты: {game_dir(record.id, games_root=games_root)}")
    return 0


def _play_game(
    resolved: dict[Side, ResolvedModel],
    *,
    settings: Settings,
    game_id: str,
    games_root: str,
    player_factory: PlayerFactory,
    engine_factory: EngineFactory,
    clock: Clock,
    max_plies: int | None,
    persist: bool,
) -> GameRecord:
    """Синхронно сыграть партию: ``GameRunner`` + ★-движок/анализ + сохранение.

    Зеркалит логику веб-``GameManager`` (но без потоков): открытый движок-или-``None``
    даёт подсказки и пост-анализ (деградация D-008/D-009), артефакты пишутся в
    ``games_root/<id>/`` (game.json + PGN + HTML).
    """
    players = {side: player_factory(side, resolved[side]) for side in _SIDES}
    record = new_game_record(
        players,  # type: ignore[arg-type]  # утиный тип игрока (.info/.respond)
        game_id=game_id,
        created_at=clock(),
        settings=settings.config.arena.to_player_settings(),
    )
    engine = engine_factory()
    try:
        GameRunner(
            players,  # type: ignore[arg-type]
            record,
            max_plies=max_plies,
            engine=engine,  # type: ignore[arg-type]
        ).play()
        _analyze(record, engine, settings)
        if persist:
            save_game(record, games_root=games_root)
            export_pgn(record, games_root=games_root)
            export_report(record, games_root=games_root)
    finally:
        if engine is not None:
            engine.close()  # type: ignore[attr-defined]
    return record


def _analyze(record: GameRecord, engine: object | None, settings: Settings) -> None:
    """★ Пост-анализ партии движком (D-009), если движок и анализ включены."""
    analysis_cfg = settings.config.analysis
    if engine is None or not analysis_cfg.enabled:
        return
    try:
        record.analysis = analyze_game(
            record,
            engine,  # type: ignore[arg-type]
            thresholds=ClassificationThresholds.from_config(analysis_cfg),
            depth=settings.config.engine.analysis_depth,
        )
    except EngineUnavailableError:
        pass  # движок отвалился — без разметки, артефакты валидны


# --- команда: турнир ------------------------------------------------------


def cmd_tournament(
    args: argparse.Namespace,
    *,
    settings: Settings,
    player_factory: TournamentPlayerFactory | None = None,
    engine_factory: EngineFactory | None = None,
    clock: Clock = _utcnow,
    out: Writer = print,
) -> int:
    """Сыграть round-robin турнир между перечисленными моделями."""
    model_ids = list(dict.fromkeys(args.models))  # уберём случайные дубли, сохранив порядок
    if len(model_ids) < 2:
        out("Турниру нужно минимум две различные модели.")
        return 2

    catalog = ModelCatalog.from_settings(settings)
    try:
        participants = [_player_info(catalog, mid) for mid in model_ids]
    except ConfigError as exc:
        out(f"Ошибка конфигурации: {exc}")
        return 2

    # Реальная фабрика игроков резолвит ключи заранее (fail-fast до прогона).
    if player_factory is None:
        try:
            resolved = {mid: catalog.resolve(mid) for mid in model_ids}
        except ConfigError as exc:
            out(f"Ошибка конфигурации: {exc}")
            return 2
        player_factory = lambda side, info: _default_player_factory(  # noqa: E731
            side, resolved[info.model_id]
        )

    if engine_factory is None:
        engine_factory = _engine_factory_from(settings)

    tournament_id = args.id or f"t-{uuid.uuid4().hex[:8]}"
    games_root = settings.config.output.games_dir
    record = new_tournament_record(
        participants,
        tournament_id=tournament_id,
        created_at=clock(),
        double=args.double,
    )
    out(f"Турнир {tournament_id}: {len(participants)} моделей, партий: {len(record.games)}.")

    try:
        outcome = TournamentRunner(
            record,
            player_factory=player_factory,
            games_root=games_root,
            clock=clock,
            engine_factory=engine_factory,
            analysis_config=settings.config.analysis,
            analysis_depth=settings.config.engine.analysis_depth,
            persist=not args.no_persist,
            player_settings=settings.config.arena.to_player_settings(),
        ).run()
    except ProviderError as exc:
        out(f"Сбой провайдера: {exc}")
        return 1

    _print_standings(outcome.standings, out=out)
    if not args.no_persist:
        out_dir = export_tournament(
            outcome, Path(games_root) / "tournaments" / tournament_id
        )
        out(f"Итоги турнира: {out_dir}")
    return 0


def _print_standings(standings: StatsTable, *, out: Writer = print) -> None:
    """Вывести таблицу турнира в терминал (строка на модель, по убыванию очков)."""
    out("")
    out(f"{'#':<3}{'Модель':<24}{'И':>3}{'В':>3}{'Н':>3}{'П':>3}{'Очки':>6}{'%':>7}")
    for rank, row in enumerate(standings.models, start=1):
        out(
            f"{rank:<3}{row.display_name:<24}{row.games:>3}{row.wins:>3}"
            f"{row.draws:>3}{row.losses:>3}{row.points:>6.1f}{row.score_pct:>6.1f}%"
        )


# --- разбор аргументов и точка входа --------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Собрать парсер аргументов CLI ``arena``."""
    parser = argparse.ArgumentParser(
        prog="arena", description="LLM Chess Arena — прогон партий и турниров."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="путь к config.yaml (по умолчанию — в корне репозитория)",
    )
    parser.add_argument(
        "--env",
        default=str(DEFAULT_ENV_FILE),
        help="путь к .env с ключами (по умолчанию — в корне репозитория)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("models", help="показать каталог моделей и наличие ключей")

    play = sub.add_parser("play", help="сыграть одну партию WHITE vs BLACK")
    play.add_argument("white", help="id модели за белых")
    play.add_argument("black", help="id модели за чёрных")
    play.add_argument("--id", default=None, help="id партии (по умолчанию случайный)")
    play.add_argument(
        "--max-plies", type=int, default=None, help="предел полуходов (защитный)"
    )
    play.add_argument(
        "--no-persist", action="store_true", help="не сохранять артефакты на диск"
    )

    tour = sub.add_parser("tournament", help="round-robin турнир между моделями")
    tour.add_argument("models", nargs="+", help="id моделей-участников (≥2)")
    tour.add_argument(
        "--double", action="store_true", help="двойной круг (со сменой цвета)"
    )
    tour.add_argument("--id", default=None, help="id турнира (по умолчанию случайный)")
    tour.add_argument(
        "--max-plies", type=int, default=None, help="предел полуходов на партию"
    )
    tour.add_argument(
        "--no-persist", action="store_true", help="не сохранять артефакты на диск"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Точка входа консольного скрипта ``arena``. Возвращает код возврата."""
    _configure_output_encoding()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    env_file = args.env or None
    try:
        settings = Settings.load(args.config, env_file)
    except (OSError, ValueError) as exc:
        print(f"Не удалось загрузить настройки: {exc}")
        return 2

    if args.command == "models":
        return cmd_models(settings)
    if args.command == "play":
        return cmd_play(args, settings=settings)
    if args.command == "tournament":
        return cmd_tournament(args, settings=settings)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
