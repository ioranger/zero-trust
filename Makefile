TEX_DIR ?= paper
MAIN_TEX ?= template.tex
PDF := $(TEX_DIR)/$(MAIN_TEX:.tex=.pdf)
TECTONIC ?= $(firstword $(wildcard /Applications/Codex.app/Contents/Resources/plugins/openai-bundled/plugins/latex/bin/tectonic /Applications/Codex 2.app/Contents/Resources/plugins/openai-bundled/plugins/latex/bin/tectonic /Applications/ChatGPT.app/Contents/Resources/plugins/openai-bundled/plugins/latex/bin/tectonic))

.PHONY: all pdf clean

all: pdf

pdf:
	@cd "$(TEX_DIR)" && if command -v latexmk >/dev/null 2>&1; then \
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
	@rm -f "$(TEX_DIR)"/*.aux "$(TEX_DIR)"/*.bbl "$(TEX_DIR)"/*.blg "$(TEX_DIR)"/*.fdb_latexmk "$(TEX_DIR)"/*.fls "$(TEX_DIR)"/*.log "$(TEX_DIR)"/*.out "$(TEX_DIR)"/*.synctex.gz
