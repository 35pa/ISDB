#!/bin/bash
# ダブルクリックでバスケ部ノートを起動する（Mac 用）
cd "$(dirname "$0")" || exit 1
echo ""
echo " バスケ部ノートを起動しています…"
echo " （この画面を閉じるとアプリが止まります）"
echo ""
if ! command -v python3 > /dev/null 2>&1 || ! python3 --version > /dev/null 2>&1; then
  echo " Python が見つかりません。"
  echo " 表示された画面で「インストール」を押し、終わったらもう一度この「起動_Mac」をダブルクリックしてください。"
  xcode-select --install 2> /dev/null || open "https://www.python.org/downloads/"
  read -r -p " Enter キーで閉じます"
  exit 1
fi
python3 サーバー.py --demo --open
echo ""
read -r -p " アプリが止まりました。Enter キーで閉じます"
