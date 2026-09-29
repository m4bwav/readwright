#!/usr/bin/env bash
# Seeds an eval workspace with fixture/moby.epub: Moby-Dick from Project Gutenberg (ebook 2701, public domain
# in the United States; about 215,000 words, 309,000 tokens by rw.py's estimate). Nothing is committed: the
# book is downloaded at run time, or copied from $RW_EVAL_BOOKS/moby.epub when that folder holds it.
# Chapter 16 (The Ship) is split across two files inside the EPUB; chapter 17 is The Ramadan.
set -e
mkdir -p fixture
if [ -n "$RW_EVAL_BOOKS" ] && [ -f "$RW_EVAL_BOOKS/moby.epub" ]; then
  cp "$RW_EVAL_BOOKS/moby.epub" fixture/moby.epub
else
  curl -fsSL -A "readwright-evals (manual run)" -o fixture/moby.epub "https://www.gutenberg.org/ebooks/2701.epub.noimages"
fi
