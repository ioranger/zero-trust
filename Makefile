MAIN_TEX ?= template.tex
PDF := $(MAIN_TEX:.tex=.pdf)
TECTONIC ?= /Applications/Codex.app/Contents/Resources/plugins/openai-bundled/plugins/latex/bin/tectonic

.PHONY: all pdf clean

all: pdf

pdf:
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error "$(MAIN_TEX)"; \
	elif [ -x "$(TECTONIC)" ]; then \
		"$(TECTONIC)" "$(MAIN_TEX)"; \
	elif command -v pdflatex >/dev/null 2>&1; then \
		pdflatex -interaction=nonstopmode -halt-on-error "$(MAIN_TEX)"; \
		pdflatex -interaction=nonstopmode -halt-on-error "$(MAIN_TEX)"; \
	else \
		echo "No LaTeX engine found. Install latexmk/pdflatex or set TECTONIC=/path/to/tectonic."; \
		exit 1; \
	fi
	@test -f "$(PDF)"

clean:
	@rm -f *.aux *.bbl *.blg *.fdb_latexmk *.fls *.log *.out *.synctex.gz
