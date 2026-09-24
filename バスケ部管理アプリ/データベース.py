"""SQLite のスキーマ定義と接続。

すべての業務テーブルに team_id を持たせ、チーム単位でデータを閉じる（他チームとの混在防止）。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

日本時間 = timezone(timedelta(hours=9))

スキーマ = """
CREATE TABLE IF NOT EXISTS teams (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  code TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  login_id TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('coach', 'player')),
  grade TEXT NOT NULL DEFAULT '',
  position TEXT NOT NULL DEFAULT '',
  number TEXT NOT NULL DEFAULT '',
  photo TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  UNIQUE (team_id, login_id)
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS menus (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '',
  minutes INTEGER NOT NULL DEFAULT 0,
  equipment TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('練習', '試合', 'その他')),
  title TEXT NOT NULL,
  date TEXT NOT NULL,
  start_time TEXT NOT NULL DEFAULT '',
  end_time TEXT NOT NULL DEFAULT '',
  place TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  published INTEGER NOT NULL DEFAULT 1,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_team_date ON events(team_id, date);

CREATE TABLE IF NOT EXISTS event_menus (
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  menu_id INTEGER NOT NULL REFERENCES menus(id) ON DELETE CASCADE,
  sort INTEGER NOT NULL,
  PRIMARY KEY (event_id, sort)
);

CREATE TABLE IF NOT EXISTS attendance (
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('出席', '欠席', '遅刻', '早退')),
  comment TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (event_id, user_id)
);

CREATE TABLE IF NOT EXISTS event_views (
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  viewed_at TEXT NOT NULL,
  PRIMARY KEY (event_id, user_id)
);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('お知らせ', '掲示板')),
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS post_reads (
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  read_at TEXT NOT NULL,
  PRIMARY KEY (post_id, user_id)
);

CREATE TABLE IF NOT EXISTS post_comments (
  id INTEGER PRIMARY KEY,
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  scope TEXT NOT NULL CHECK (scope IN ('個人', 'チーム')),
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  deadline TEXT NOT NULL DEFAULT '',
  progress INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT '進行中' CHECK (status IN ('進行中', '達成', '未達成')),
  reflection TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  coach_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  body TEXT NOT NULL,
  reply TEXT NOT NULL DEFAULT '',
  confirmed_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tactics (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('オフェンス', 'ディフェンス')),
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  data TEXT NOT NULL,
  is_template INTEGER NOT NULL DEFAULT 0,
  published INTEGER NOT NULL DEFAULT 1,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tactic_quizzes (
  id INTEGER PRIMARY KEY,
  tactic_id INTEGER NOT NULL REFERENCES tactics(id) ON DELETE CASCADE,
  question TEXT NOT NULL,
  choices TEXT NOT NULL,
  answer_index INTEGER NOT NULL,
  explanation TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tactic_answers (
  quiz_id INTEGER NOT NULL REFERENCES tactic_quizzes(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  choice INTEGER NOT NULL,
  correct INTEGER NOT NULL,
  answered_at TEXT NOT NULL,
  PRIMARY KEY (quiz_id, user_id)
);

CREATE TABLE IF NOT EXISTS tactic_checks (
  tactic_id INTEGER NOT NULL REFERENCES tactics(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  understood INTEGER NOT NULL,
  comment TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (tactic_id, user_id)
);

CREATE TABLE IF NOT EXISTS issues (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT '取組中' CHECK (status IN ('取組中', '解決')),
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stats (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  minutes INTEGER NOT NULL DEFAULT 0,
  points INTEGER NOT NULL DEFAULT 0,
  rebounds INTEGER NOT NULL DEFAULT 0,
  assists INTEGER NOT NULL DEFAULT 0,
  steals INTEGER NOT NULL DEFAULT 0,
  blocks INTEGER NOT NULL DEFAULT 0,
  turnovers INTEGER NOT NULL DEFAULT 0,
  fgm INTEGER NOT NULL DEFAULT 0,
  fga INTEGER NOT NULL DEFAULT 0,
  tpm INTEGER NOT NULL DEFAULT 0,
  tpa INTEGER NOT NULL DEFAULT 0,
  ftm INTEGER NOT NULL DEFAULT 0,
  fta INTEGER NOT NULL DEFAULT 0,
  zones TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stats_player ON stats(player_id, date);

CREATE TABLE IF NOT EXISTS practice_logs (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  minutes INTEGER NOT NULL DEFAULT 0,
  content TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_categories (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  sort INTEGER NOT NULL DEFAULT 0,
  UNIQUE (team_id, name)
);

CREATE TABLE IF NOT EXISTS skill_assessments (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category_id INTEGER NOT NULL REFERENCES skill_categories(id) ON DELETE CASCADE,
  source TEXT NOT NULL CHECK (source IN ('コーチ', '自己評価')),
  value INTEGER NOT NULL CHECK (value BETWEEN 0 AND 100),
  assessor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  assessed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assess_player ON skill_assessments(player_id, category_id, source);

CREATE TABLE IF NOT EXISTS drill_steps (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  category_id INTEGER NOT NULL REFERENCES skill_categories(id) ON DELETE CASCADE,
  level TEXT NOT NULL CHECK (level IN ('基礎', '初級', '中級', '上級', 'プロ')),
  step_no INTEGER NOT NULL DEFAULT 1,
  title TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  minutes INTEGER NOT NULL DEFAULT 10,
  clear_condition TEXT NOT NULL DEFAULT '',
  next_step_id INTEGER REFERENCES drill_steps(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS player_step_progress (
  player_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  drill_id INTEGER NOT NULL REFERENCES drill_steps(id) ON DELETE CASCADE,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('未着手', '実施中', '完了')),
  self_rating INTEGER NOT NULL DEFAULT 0,
  report TEXT NOT NULL DEFAULT '',
  video_url TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (player_id, drill_id)
);

CREATE TABLE IF NOT EXISTS step_reports (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  drill_id INTEGER NOT NULL REFERENCES drill_steps(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  self_rating INTEGER NOT NULL,
  comment TEXT NOT NULL DEFAULT '',
  video_url TEXT NOT NULL DEFAULT '',
  cleared INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS step_overrides (
  player_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category_id INTEGER NOT NULL REFERENCES skill_categories(id) ON DELETE CASCADE,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  drill_id INTEGER NOT NULL REFERENCES drill_steps(id) ON DELETE CASCADE,
  note TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (player_id, category_id)
);
"""


def 現在時刻() -> str:
    return datetime.now(日本時間).isoformat(timespec="seconds")


def 今日() -> str:
    return datetime.now(日本時間).date().isoformat()


def 接続(パス: str | Path) -> sqlite3.Connection:
    接続先 = sqlite3.connect(str(パス), timeout=10, check_same_thread=False)
    接続先.row_factory = sqlite3.Row
    接続先.execute("PRAGMA foreign_keys = ON")
    if str(パス) != ":memory:":
        接続先.execute("PRAGMA journal_mode = WAL")
    return 接続先


def 初期化(接続先: sqlite3.Connection) -> None:
    接続先.executescript(スキーマ)
    _旧バージョンのデータを更新(接続先)
    接続先.commit()


def _旧バージョンのデータを更新(接続先: sqlite3.Connection) -> None:
    """以前のバージョンで作ったデータベースを、今のバージョンで使える形にそろえる。"""
    # ドリルのレベルが3段階（初級・中級・上級）だった頃の表を、5段階（基礎〜プロ）を入れられる表に作り直す
    定義 = 接続先.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'drill_steps'").fetchone()[0]
    if "'基礎'" not in 定義:
        新しい定義 = スキーマ.split("CREATE TABLE IF NOT EXISTS drill_steps", 1)[1].split(");", 1)[0] + ");"
        接続先.commit()
        接続先.execute("PRAGMA foreign_keys = OFF")
        try:
            接続先.executescript(
                f"""BEGIN;
                CREATE TABLE drill_steps_新 {新しい定義}
                INSERT INTO drill_steps_新 SELECT * FROM drill_steps;
                DROP TABLE drill_steps;
                ALTER TABLE drill_steps_新 RENAME TO drill_steps;
                COMMIT;"""
            )
        finally:
            接続先.execute("PRAGMA foreign_keys = ON")
    # スキル名「フィジカル」は「基礎体力」に変更（同じチームに「基礎体力」が既にあれば変更しない）
    接続先.execute(
        """UPDATE skill_categories SET name = '基礎体力' WHERE name = 'フィジカル'
           AND NOT EXISTS (SELECT 1 FROM skill_categories AS c WHERE c.team_id = skill_categories.team_id AND c.name = '基礎体力')"""
    )


def 行を辞書に(行: sqlite3.Row | None) -> dict | None:
    return dict(行) if 行 is not None else None


def 行一覧を辞書に(行一覧) -> list[dict]:
    return [dict(行) for 行 in 行一覧]
