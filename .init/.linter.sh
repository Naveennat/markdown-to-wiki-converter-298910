#!/bin/bash
cd /home/kavia/workspace/code-generation/markdown-to-wiki-converter-298910/markdown_wiki_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

