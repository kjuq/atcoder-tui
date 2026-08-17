# atcoder-tui

!! **CAUTION: このソフトウェアは開発途中です。使用して生じた何如なる問題について責任を持ちません。特にコンテスト本番での使用は避けるようお願いします** !!

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
uv run atcoder-tui
```

起動後の流れ:

1. `/` でコンテスト検索を開き、`abc100` のように打ち込んで絞り込み、Enter で選択
2. 左上の一覧で問題を選び Enter -> 右に問題文が表示される
3. `t` でローカルのソースをサンプルテスト
4. `L` でログインし、`s` で提出 (確認ダイアログあり)

コンテスト一覧は初回に AtCoder のアーカイブ全体を取得してローカルにキャッシュします (数十秒)。以降は即座に表示され、検索画面で `Ctrl+R` を押すと再取得できます。

最後に読み込んだコンテストは設定に保存され、次回起動時に自動で問題一覧を読み込みます。

提出やテストに使うソースファイルは、`ATCODER_TUI_REPO_BASE` に設定したリポジトリから自動で読み込みます。
問題 `abc471/A` なら、次のパスを使用します。

```text
$ATCODER_TUI_REPO_BASE/abc471/a/main.py
```

言語はホーム画面で `w` を押して選択します。選択中の言語はステータスバーに表示され、設定は終了後も保持されます。

### 言語一覧の更新

提出言語の一覧は [AtCoder の公式言語一覧](https://img.atcoder.jp/file/language-update/2025-10/language-list.html) を元に、`src/atcoder_tui/data/languages.json` に保存しています。AtCoder で言語やバージョンが更新されたときは、リポジトリのルートで次を実行してください。

```bash
uv run python scripts/update_languages.py
```

AtCoder が新しい言語一覧ページを公開して既定 URL が変わった場合は、URL を指定します。

```bash
uv run python scripts/update_languages.py \
  --url https://img.atcoder.jp/file/language-update/YYYY-MM/language-list.html
```

更新前に差分だけ確認する場合は `--check` を使えます。更新後は `languages.json` の差分を確認してコミットしてください。言語名・ファイル拡張子の抽出はスクリプトが行いますが、ローカルのサンプルテスト用コマンドは `src/atcoder_tui/tester.py` で管理しています。

### ログインについて

AtCoder のログインフォームは Cloudflare Turnstile (CAPTCHA の一種) で保護されているため、ユーザ名/パスワードを HTTP で送るだけのログインはできません。本ツールはブラウザのセッション Cookie を取り込む方式を採用しています。

1. `L` でログイン画面を開く
2. 「ブラウザを開く」で AtCoder にログイン
3. ブラウザの開発者ツール → Application/ストレージ → Cookies → `https://atcoder.jp` を開き、`REVEL_SESSION` の値をコピー
4. ログイン画面に貼り付けてログイン

#### 提出と CAPTCHA

AtCoder は、ログインだけでなくソースコード提出やカスタムテストにも Cloudflare Turnstile (CAPTCHA) を導入しています。CAPTCHA が要求されない状況では `oj` / `oj-api` によるターミナルからの提出が可能ですが、CAPTCHA が要求される提出を `oj` が自動的に通過させることはできません。特に終了済みコンテストでは、ターミナルからの提出が拒否される場合があります。

`oj` の AtCoder 対応は、提出ページから CSRF トークンを取得し、問題 ID・言語 ID・ソースコードを通常の HTML フォームとして POST する実装です。CAPTCHA トークンを取得・送信する処理はありません。`oj login` も AtCoder の CAPTCHA の影響を受けるため、ブラウザでログインした後に `REVEL_SESSION` Cookie を `oj` の Cookie jar に取り込む方法が使われますが、これは提出時の CAPTCHA を解決するものではありません。

今回の確認では、`oj` の問題ページ解析で `AssertionError: assert parsed_memory_limit` が発生するケースも確認しました。これは CAPTCHA とは別の、AtCoder の HTML 変更に対する `oj` の互換性問題です。

このため、`s` はターミナルから提出を試みず、確認ダイアログで Enter を押すと AtCoder の問題ページをブラウザで開きます。CAPTCHA の完了と提出操作はブラウザで行ってください。

## キーバインド

| キー | 機能 |
| --- | --- |
| `/` | コンテストを検索して選ぶ (`abc100` などで絞り込み。`c` も可) |
| `Enter` | 問題一覧で選択中の問題を開く |
| `t` | サンプルテストを実行 |
| `s` | 選択中の問題に提出 (確認あり) |
| `S` | 自分の提出一覧を確認 |
| `r` | 選択中の問題をブラウザで開く |
| `L` | ログイン |
| `w` | 提出言語を変更 |
| `1` / `2` / `3` | 各パネル (問題一覧 / 結果 / 本文) へフォーカス |
| `h` / `l` / `Tab` | パネル間を移動 (lazygit 風。検索欄はスキップ) |
| `j` / `k` | パネル内を上下移動 (矢印キーと同じ) |
| `?` | ヘルプ表示 |
| `q` | 終了 |

## テスト対象の言語

サンプルテストは拡張子からコンパイル/実行方法を判定します。対応拡張子: `.py` `.cpp` `.cc` `.c` `.rs` `.go` `.js`。コンパイル系はそれぞれ `g++` / `gcc` / `rustc` などが必要です。

## 設定/セッション

ログインセッション (cookie) とコンテスト一覧は [platformdirs](https://github.com/tox-dev/platformdirs) が示すユーザ設定ディレクトリ配下に保存されます。問題文 Markdown は `$XDG_CACHE_HOME/atcoder-tui`、提出言語と最後に開いたコンテスト/問題は `$XDG_STATE_HOME/atcoder-tui` に保存されます。未設定時はそれぞれ XDG 標準の `~/.cache/atcoder-tui`、`~/.local/state/atcoder-tui` を使用します。

## 開発

```bash
uv run pytest
```

## 注意

このツールは AtCoder のページをスクレイピングして動作します。利用は自己責任で、AtCoder への過度なリクエストを避けてください。提出は必ず確認ダイアログを挟みます。
