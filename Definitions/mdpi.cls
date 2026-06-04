% Lightweight MDPI-compatible class shim for local compilation.
% It supports the subset of MDPI macros used by template.tex.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{Definitions/mdpi}[2026/06/02 Local MDPI compatibility class]

\DeclareOption*{\@namedef{opt@\CurrentOption.cls}{}}
\ProcessOptions\relax
\LoadClass[10pt,a4paper]{article}

\RequirePackage{iftex}
\ifXeTeX
  \PassOptionsToPackage{xetex}{graphicx}
  \PassOptionsToPackage{xetex}{xcolor}
\fi
\ifLuaTeX
  \PassOptionsToPackage{luatex}{graphicx}
  \PassOptionsToPackage{luatex}{xcolor}
\fi

\RequirePackage[T1]{fontenc}
\RequirePackage[utf8]{inputenc}
\RequirePackage{geometry}
\geometry{margin=1in}
\RequirePackage{amsmath}
\RequirePackage{amssymb}
\RequirePackage{amsthm}
\RequirePackage{array}
\RequirePackage{booktabs}
\RequirePackage{caption}
\RequirePackage{enumitem}
\RequirePackage{float}
\RequirePackage{graphicx}
\RequirePackage{microtype}
\RequirePackage{multirow}
\RequirePackage[numbers,sort&compress]{natbib}
\RequirePackage{tabularx}
\RequirePackage{xcolor}
\RequirePackage{hyperref}
\RequirePackage[capitalise,nameinlink]{cleveref}

\hypersetup{
  colorlinks=true,
  linkcolor=blue!55!black,
  citecolor=blue!55!black,
  urlcolor=blue!55!black,
  pdftitle={MARL-based Trust Evaluation for Zero-Trust Low-Altitude UAV Networks}
}

\setlength{\parindent}{1.5em}
\setlength{\parskip}{0.35em}
\setlist[itemize]{leftmargin=*,itemsep=0.25em,topsep=0.35em}
\setlist[enumerate]{leftmargin=*,itemsep=0.25em,topsep=0.35em}
\captionsetup{font=small,labelfont=bf}

\makeatletter
\newcommand{\@PaperTitle}{}
\newcommand{\@PaperAuthor}{}
\newcommand{\@PaperAuthorNames}{}
\newcommand{\@PaperAddress}{}
\newcommand{\@PaperCorrespondence}{}
\newcommand{\@PaperAbstract}{}
\newcommand{\@PaperKeywords}{}
\newcommand{\@firstpage}{1}

\newcommand{\Title}[1]{\gdef\@PaperTitle{#1}\title{#1}}
\newcommand{\Author}[1]{\gdef\@PaperAuthor{#1}\author{#1}}
\newcommand{\AuthorNames}[1]{\gdef\@PaperAuthorNames{#1}}
\newcommand{\address}[1]{\gdef\@PaperAddress{#1}}
\newcommand{\corres}[1]{\gdef\@PaperCorrespondence{#1}}
\renewcommand{\abstract}[1]{\gdef\@PaperAbstract{#1}}
\newcommand{\keyword}[1]{\gdef\@PaperKeywords{#1}}

\newcommand{\firstpage}[1]{\gdef\@firstpage{#1}}
\newcommand{\pubvolume}[1]{}
\newcommand{\issuenum}[1]{}
\newcommand{\articlenumber}[1]{}
\newcommand{\pubyear}[1]{}
\newcommand{\copyrightyear}[1]{}
\newcommand{\datereceived}[1]{}
\newcommand{\daterevised}[1]{}
\newcommand{\dateaccepted}[1]{}
\newcommand{\datepublished}[1]{}
\newcommand{\doinum}[1]{}
\newcommand{\CorrStatement}[1]{}
\newcommand{\longauthorlist}[1]{}
\newcommand{\IsAssociation}[1]{}
\newcommand{\simplesumm}[1]{}
\newcommand{\conference}[1]{}
\newcommand{\featuredapplication}[1]{}
\newcommand{\dataset}[1]{}
\newcommand{\datasetlicense}[1]{}
\newcommand{\keycontribution}[1]{}
\newcommand{\encyclopediadef}[1]{}
\newcommand{\addhighlights}{}
\newcommand{\orcidA}{}
\newcommand{\orcidB}{}
\newcommand{\linksupplementary}[1]{#1}
\newcommand{\newmarginnote}[2]{}

\newcommand{\reftitle}[1]{\section*{#1}}
\renewenvironment{thebibliography}[1]
  {\list{\@biblabel{\@arabic\c@enumiv}}%
    {\settowidth\labelwidth{\@biblabel{#1}}%
     \leftmargin\labelwidth
     \advance\leftmargin\labelsep
     \usecounter{enumiv}%
     \let\p@enumiv\@empty
     \renewcommand\theenumiv{\@arabic\c@enumiv}}%
   \sloppy\clubpenalty4000\widowpenalty4000%
   \sfcode`\.=\@m}
  {\def\@noitemerr{\@latex@warning{Empty `thebibliography' environment}}%
   \endlist}
\newcommand{\authorcontributions}[1]{\section*{Author Contributions}#1}
\newcommand{\funding}[1]{\section*{Funding}#1}
\newcommand{\institutionalreview}[1]{\section*{Institutional Review Board Statement}#1}
\newcommand{\informedconsent}[1]{\section*{Informed Consent Statement}#1}
\newcommand{\dataavailability}[1]{\section*{Data Availability Statement}#1}
\newcommand{\conflictsofinterest}[1]{\section*{Conflicts of Interest}#1}

\AtBeginDocument{%
  \begin{center}
    {\LARGE\bfseries \@PaperTitle\par}
    \vspace{0.75em}
    {\large \@PaperAuthor\par}
    \vspace{0.5em}
    {\small \@PaperAddress\par}
    \vspace{0.25em}
    {\small \@PaperCorrespondence\par}
  \end{center}
  \vspace{0.75em}
  \noindent\textbf{Abstract:} \@PaperAbstract\par
  \vspace{0.4em}
  \noindent\textbf{Keywords:} \@PaperKeywords\par
  \vspace{1em}
}
\makeatother
