"""
Document Parsing

checks.py (raw-byte upload checks) → sandbox.py + worker.py (pdf.py, docx.py, text.py in a
resource-limited subprocess) or docling.py (optional docling-serve container).

Keep this file free of imports: worker.py runs as `python -I -m app.parsing.worker`, which
imports this package first, and the worker must not pull in app.config (it has no environment
and no business reading the service's settings).
"""
