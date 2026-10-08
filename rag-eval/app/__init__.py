"""
EduAvatars Evaluation Service

Ragas sends anonymous usage analytics unless RAGAS_DO_NOT_TRACK is "true". It's forced here,
before anything can import ragas, so no deployment can switch it on by accident: this service
handles teachers' material and their keys, and has no business reporting anything elsewhere.
"""

import os

os.environ["RAGAS_DO_NOT_TRACK"] = "true"
