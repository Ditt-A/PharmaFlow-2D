"""Preserve learned/frozen artifacts while making forest inference reductions serial."""
import joblib
from .m4_models import predict as original_predict


def predict(artifact, features):
    # M4A observed ~1e-16 forest reduction roundoff. This changes neither tree
    # parameters nor stored n_jobs, and is applied before all M4B OOF selection.
    with joblib.parallel_backend('sequential'):
        return original_predict(artifact, features)
