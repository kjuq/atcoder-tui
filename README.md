# atcoder-cli

AtCoder の問題を閲覧・テスト・提出できる lazygit 風の TUI ツールです。Python + [Textual](https://textual.textualize.io/) 製。

問題ページ (HTML) は [defuddle](https://github.com/kepano/defuddle) で Markdown に変換して表示します。

## 機能

- コンテストの問題一覧の表示と問題本文の閲覧 (Markdown 化)
- 数式 (KaTeX/LaTeX) を端末向けの Unicode 近似 (例 `1≤N≤2×10⁵`) に変換して表示
- サンプル入出力の抽出と、ローカルソースでのサンプルテスト (AC / WA / RE / TLE / CE 判定)
- AtCoder へのログインとコード提出 (提出前に確認ダイアログあり)
- 自分の提出結果の確認

## 前提

- Python 3.12 以上
- [uv](https://docs.astral.sh/uv/)
- Node.js + npx (`defuddle` を実行するために必要。無い場合は簡易変換にフォールバックします)

## セットアップ

```bash
uv sync
```

## 使い方

```bash
uv run atcoder-cli
```

起動後の流れ:

1. `c` を押してコンテストID (例 `abc086`) を入力し Enter
2. 左上の一覧で問題を選び Enter -> 右に問題文が表示される
3. `t` でローカルのソースをサンプルテスト
4. `L` でログインし、`s` で提出 (確認ダイアログあり)

提出やテストに使うソースファイルは、その都度パスを入力します。初期値として `{task_id}.py` (例 `abc086_a.py`) を提案します。

### ログインについて

AtCoder のログインフォームは Cloudflare Turnstile (CAPTCHA の一種) で保護されているため、ユーザ名/パスワードを HTTP で送るだけのログインはできません。本ツールはブラウザのセッション Cookie を取り込む方式を採用しています。

1. `L` でログイン画面を開く
2. 「ブラウザを開く」で AtCoder にログイン
3. ブラウザの開発者ツール → Application/ストレージ → Cookies → `https://atcoder.jp` を開き、`REVEL_SESSION` の値をコピー
4. ログイン画面に貼り付けてログイン

一度ログインすればセッションが保存され、提出 (`s`) や提出一覧 (`S`) はそのまま利用できます (これらは CAPTCHA の対象外です)。

## キーバインド

| キー | 機能 |
| --- | --- |
| `/` | コンテストID 入力欄 (検索) へフォーカス (`c` も可) |
| `Enter` | 問題一覧で選択中の問題を開く |
| `t` | サンプルテストを実行 |
| `s` | 選択中の問題に提出 (確認あり) |
| `S` | 自分の提出一覧を確認 |
| `r` | 選択中の問題をブラウザで開く |
| `L` | ログイン |
| `1` / `2` / `3` | 各パネル (問題一覧 / 結果 / 本文) へフォーカス |
| `h` / `l` / `Tab` | パネル間を移動 (lazygit 風。検索欄はスキップ) |
| `j` / `k` | パネル内を上下移動 (矢印キーと同じ) |
| `?` | ヘルプ表示 |
| `q` | 終了 |

## テスト対象の言語

サンプルテストは拡張子からコンパイル/実行方法を判定します。対応拡張子: `.py` `.cpp` `.cc` `.c` `.rs` `.go` `.js`。コンパイル系はそれぞれ `g++` / `gcc` / `rustc` などが必要です。

## 設定/セッション

ログインセッション (cookie) は [platformdirs](https://github.com/tox-dev/platformdirs) が示すユーザ設定ディレクトリ配下に保存されます (macOS なら `~/Library/Application Support/atcoder-cli/session.txt`)。パスワードは扱わず、ブラウザから取り込んだセッション Cookie (`REVEL_SESSION`) のみを保存します。

## 開発

```bash
uv run pytest
```

## 注意

このツールは AtCoder のページをスクレイピングして動作します。利用は自己責任で、AtCoder への過度なリクエストを避けてください。提出は必ず確認ダイアログを挟みます。
