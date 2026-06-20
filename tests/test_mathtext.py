"""mathtext モジュールのテスト (LaTeX -> Unicode 変換と HTML 前処理)。"""

from __future__ import annotations

from pathlib import Path

from atcoder_tui.mathtext import latex_to_unicode, preprocess_math

FIXTURES = Path(__file__).parent / "fixtures"


def test_operators_and_greek() -> None:
	# 関係/二項演算子の両側にはスペースが入る。
	assert latex_to_unicode(r"a \leq b") == "a ≤ b"
	assert latex_to_unicode(r"\alpha + \beta").startswith("α")
	assert "×" in latex_to_unicode(r"2 \times 3")
	assert "…" in latex_to_unicode(r"a_1, \ldots, a_n")


def test_operator_spacing() -> None:
	# 元の LaTeX に空白が無くても両側に 1 つずつスペースを入れる。
	assert latex_to_unicode(r"N\leq10^9") == "N ≤ 10⁹"
	assert latex_to_unicode(r"a\times b") == "a × b"
	assert latex_to_unicode(r"x=y") == "x = y"
	# スペースが重複しない。
	assert latex_to_unicode(r"a \leq  b") == "a ≤ b"


def test_superscripts() -> None:
	assert latex_to_unicode(r"10^5") == "10⁵"
	assert latex_to_unicode(r"10^{18}") == "10¹⁸"
	assert latex_to_unicode(r"2 \times 10 ^ 5") == "2 × 10⁵"
	# 数字の積み重ね
	assert latex_to_unicode(r"1\leq N\leq2\times10 ^ 5") == "1 ≤ N ≤ 2 × 10⁵"


def test_subscripts() -> None:
	assert latex_to_unicode(r"a_i") == "aᵢ"
	assert latex_to_unicode(r"a_{i+1}") == "aᵢ₊₁"
	assert latex_to_unicode(r"X_1") == "X₁"


def test_unmappable_script_fallback() -> None:
	# 大文字 N は上付きにできないので括弧フォールバック。
	assert latex_to_unicode(r"2^{N-1}") == "2^(N-1)"
	# 添字のカンマも括弧フォールバック。
	assert latex_to_unicode(r"A_{i,j}") == "A_(i,j)"


def test_preprocess_var_tags() -> None:
	html = r"<ul><li><var>1\leq N\leq2\times10 ^ 5</var></li></ul>"
	out = preprocess_math(html)
	assert "1 ≤ N ≤ 2 × 10⁵" in out
	assert "<var>" not in out
	assert "\\leq" not in out


def test_preprocess_keeps_pre_untouched() -> None:
	# サンプル入出力 (pre) 内は数式変換しない。
	html = "<pre>3 4\n10^5 not math here</pre>"
	out = preprocess_math(html)
	assert "10^5 not math here" in out


def test_preprocess_dollar_delimiters() -> None:
	html = r"<p>制約は $N \leq 10^9$ です。</p>"
	out = preprocess_math(html)
	assert "N ≤ 10⁹" in out
	assert "$" not in out


def test_sample_problem_constraints() -> None:
	html = (FIXTURES / "sample_math.html").read_text(encoding="utf-8")
	out = preprocess_math(html)
	# 制約に出てくる上限値が Unicode 化されている。
	assert "2 × 10⁵" in out
	# サンプル (pre 内) の文字列は数式変換の対象外で壊れていない。
	assert "ABABBA" in out
