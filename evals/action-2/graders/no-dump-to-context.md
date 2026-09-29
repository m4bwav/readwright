---
type: tool_used
name: 'no whole-book dump into the context (unzip -p, epr -d, pandoc or markitdown to stdout, or --max-chars of 100,000 or more)'
tool: Bash
input_match: 'unzip\s+-p|epr\s+-d|pandoc\s(?![^|;&]*\s-o\s)[^|;&]*-t\s*plain|markitdown\s(?![^|;&]*\s-o\s)[^|;&>]*$|--max-chars[=\s]+[1-9]\d{5,}'
min: 0
max: 0
---
