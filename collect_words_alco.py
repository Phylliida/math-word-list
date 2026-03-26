#for the .tex file in an alco folder (at the base level, not the original/old copy inside)

#(sanity check: the correct style file should appear in the first 5 lines)

# parse the .tex into a simplified string; 
#   we include the abstract and title and institution names

#   we skip everything else before \begin{document}

#   we skip all mathmode (including the contents of \begin{equation} and \end{equation})

#   we skip everything commented out %...

#   we remove extra spacing commands, especially between words, eg `grassman-\newline-nian` -> 'grassmannian'

#   we include text inside of \text{} and \caption{} and \texorpdfstring[]{} (still removing any math) 

#   we remove text inside of tikzpicture, tikzcd, labels

#   we remove \emph, \textbf, and similar macros (but keep their arguments)

#   we include alt-text from figures

#   we include section titles 

#   we include the replacement/additional display text for theorems, so both of theorem[]{}.

#   we do not include the bibtex labels from \cite{}