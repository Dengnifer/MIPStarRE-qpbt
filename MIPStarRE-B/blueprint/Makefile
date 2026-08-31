PYTHON ?= python3
LATEXMK ?= latexmk
DOT ?= dot

.PHONY: check generate test pdf graph clean

check:
	$(PYTHON) check.py --check

generate:
	$(PYTHON) check.py --write

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

graph: check
	$(DOT) -Tsvg generated/graph.dot -o generated/graph.svg

pdf: check
	mkdir -p build
	$(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error -outdir=build src/main.tex
	$(PYTHON) check_pdf.py build/main.pdf

clean:
	$(LATEXMK) -C -outdir=build src/main.tex
