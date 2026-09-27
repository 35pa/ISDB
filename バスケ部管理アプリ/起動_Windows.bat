@echo off
chcp 65001 > nul
cd /d "%~dp0"
title バスケ部ノート
echo.
echo  バスケ部ノートを起動しています…
echo  （この黒い画面を閉じるとアプリが止まります）
echo.

set "PYTHON="
py -3 --version > nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON (
  python --version > nul 2>&1 && set "PYTHON=python"
)

if not defined PYTHON (
  echo  Python が見つからないため、自動でインストールします（数分かかります）。
  echo  途中で「このアプリがデバイスに変更を加えることを許可しますか？」と出たら「はい」を押してください。
  echo.
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo.
    echo  自動インストールができませんでした。開いたページから Python をインストールしてください。
    echo  インストール画面では「Add python.exe to PATH」に必ずチェックを入れてください。
    start "" "https://www.python.org/downloads/"
  ) else (
    echo.
    echo  インストールが終わりました。もう一度この「起動_Windows」をダブルクリックしてください。
  )
  echo.
  pause
  exit /b
)

%PYTHON% サーバー.py --demo --open
echo.
echo  アプリが止まりました。
pause
