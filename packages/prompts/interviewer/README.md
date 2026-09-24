# Interviewer prompts

`v1.md` is a `string.Template` rendered by `app/interview/interviewer.py`. Every rendered
call records `interviewer/v1+<sha8>` as its prompt version, so any edit is traceable. Bump the
file version (v2.md) for behavioral changes and keep the old file for replay and comparison.
