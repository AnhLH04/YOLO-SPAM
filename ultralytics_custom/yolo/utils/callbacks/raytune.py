try:
    import ray
    from ray import tune
    from ray.air import session
except (ImportError, AssertionError):
    tune = None


def on_fit_epoch_end(trainer):
    """Sends training metrics to Ray Tune at end of each epoch."""
    if session.get_session() is not None:
        metrics = trainer.metrics
        metrics['epoch'] = trainer.epoch
        session.report(metrics)


callbacks = {
    'on_fit_epoch_end': on_fit_epoch_end, } if tune else {}
