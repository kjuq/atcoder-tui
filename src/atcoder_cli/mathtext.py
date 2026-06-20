"""AtCoder の問題に埋め込まれた LaTeX (KaTeX) を端末向けの Unicode へ変換する。

AtCoder の問題ページは数式を KaTeX でクライアント側レンダリングしており、
サーバが返す生 HTML には LaTeX ソースがそのまま含まれる。主に ``<var>`` タグ、
場合によっては ``$...$`` / ``\\(...\\)`` 区切りで現れる。

端末では本物の数式組版はできないため、演算子やギリシャ文字を Unicode 記号へ、
上付き/下付きを Unicode の上付き/下付き文字へ近似変換して読めるようにする。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag
from pylatexenc.latex2text import LatexNodes2Text

# 上付き・下付きに使える文字。対応表に無い文字を含む場合はフォールバックする。
_SUP_SRC = "0123456789+-=()n"
_SUP_DST = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ"
_SUB_SRC = "0123456789+-=()aehijklmnoprstuvx"
_SUB_DST = "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"
_SUP = str.maketrans(_SUP_SRC, _SUP_DST)
_SUB = str.maketrans(_SUB_SRC, _SUB_DST)

# braced group を残したまま \command を変換させる。
_CONV = LatexNodes2Text(keep_braced_groups=True, keep_braced_groups_minlen=1)

# 両側に空白を入れると読みやすい二項演算子・関係演算子。
# (+ と - は符号や範囲表記、上付き/下付きのフォールバックを壊すため対象外)
_SPACED_OPS = "=≠<>≤≥≪≫×÷·±∓∈∉∣∧∨∪∩⊕⊗⊆⊂⊇⊃≡≈→"
_OP_SPACING = re.compile(rf"[ \t]*([{_SPACED_OPS}])[ \t]*")

# テキストノード中の数式区切り ($...$, $$...$$, \(...\), \[...\])。
_MATH_SPANS = re.compile(
	r"\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]",
	re.DOTALL,
)

# 数式を解釈してはいけない要素 (サンプル入出力やコードなど)。
_SKIP_PARENTS = {"pre", "code", "script", "style", "textarea"}


def _render_script(body: str, src: str, table: dict[int, int], op: str) -> str:
	"""上付き/下付きの中身を変換する。全文字が対応表にあれば Unicode 化。"""
	if body.startswith("{") and body.endswith("}"):
		body = body[1:-1]
	if body and all(c in src for c in body):
		return body.translate(table)
	# 対応外: 1 文字はそのまま、複数文字は括弧で括って曖昧さを避ける。
	return f"{op}{body}" if len(body) == 1 else f"{op}({body})"


def _apply_scripts(text: str) -> str:
	text = re.sub(
		r"\s*\^\s*(\{[^{}]*\}|\S)",
		lambda m: _render_script(m.group(1), _SUP_SRC, _SUP, "^"),
		text,
	)
	text = re.sub(
		r"\s*_\s*(\{[^{}]*\}|\S)",
		lambda m: _render_script(m.group(1), _SUB_SRC, _SUB, "_"),
		text,
	)
	return text


def _space_operators(text: str) -> str:
	"""関係/二項演算子の両側を単一スペースに正規化する。"""
	return _OP_SPACING.sub(r" \1 ", text)


def latex_to_unicode(latex: str) -> str:
	"""LaTeX 断片を Unicode 近似テキストへ変換する。"""
	if not latex.strip():
		return latex
	# 先に \command 等を変換 (braced group は保持)、その後で上付き/下付きを処理。
	converted = _CONV.latex_to_text(latex)
	converted = _apply_scripts(converted)
	# 演算子の周りにスペースを入れ、余分な空白を整理する。
	converted = _space_operators(converted)
	converted = re.sub(r"[ \t]{2,}", " ", converted)
	return converted.strip()


def _convert_text_node(text: str) -> str:
	"""テキスト中の数式区切りで囲まれた部分だけを変換する。"""

	def repl(match: re.Match[str]) -> str:
		inner = next(g for g in match.groups() if g is not None)
		return latex_to_unicode(inner)

	return _MATH_SPANS.sub(repl, text)


def preprocess_math(html: str) -> str:
	"""問題本文 HTML 内の LaTeX を Unicode 化した HTML を返す。

	defuddle / フォールバック変換の前段として呼ぶ。``<var>`` の中身は必ず数式
	として扱い、それ以外のテキストは数式区切りがある場合のみ変換する。
	"""
	soup = BeautifulSoup(html, "lxml")

	# <var> は確実に数式。中身を変換してプレーンテキストに置き換える。
	for var in soup.find_all("var"):
		converted = latex_to_unicode(var.get_text())
		var.replace_with(NavigableString(converted))

	# 残りのテキストノードは、明示的な数式区切りがある場合のみ変換する。
	for node in list(soup.find_all(string=True)):
		if not isinstance(node, NavigableString):
			continue
		parent = node.parent
		if isinstance(parent, Tag) and parent.name in _SKIP_PARENTS:
			continue
		raw = str(node)
		if "$" not in raw and "\\(" not in raw and "\\[" not in raw:
			continue
		replaced = _convert_text_node(raw)
		if replaced != raw:
			node.replace_with(NavigableString(replaced))

	body = soup.body
	if body is not None:
		return body.decode_contents()
	return str(soup)
