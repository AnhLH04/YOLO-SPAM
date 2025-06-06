# Ultralytics YOLO 🚀, AGPL-3.0 license
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from ultralytics_custom.yolo.utils import LOGGER, TESTS_RUNNING
from ultralytics_custom.yolo.utils.torch_utils import get_flops, get_num_params

try:
    import neptune
    from neptune.types import File

    assert not TESTS_RUNNING  # do not log pytest
    assert hasattr(neptune, '__version__')
except (ImportError, AssertionError):
    neptune = None

run = None  # NeptuneAI experiment logger instance


def _log_scalars(scalars, step=0):
    """Log scalars to the NeptuneAI experiment logger."""
    if run:
        for k, v in scalars.items():
            run[k].append(value=v, step=step)


def _log_images(imgs_dict, group=''):
    """Log scalars to the NeptuneAI experiment logger."""
    if run:
        for k, v in imgs_dict.items():
            run[f'{group}/{k}'].upload(File(v))


def _log_plot(title, plot_path):
    """Log plots to the NeptuneAI experiment logger."""
    """
        Log image as plot in the plot section of NeptuneAI

        arguments:
        title (str) Title of the plot
        plot_path (PosixPath or str) Path to the saved image file
        """
    img = mpimg.imread(plot_path)
    fig = plt.figure()
    ax = fig.add_axes([0, 0, 1, 1], frameon=False, aspect='auto', xticks=[], yticks=[])  # no ticks
    ax.imshow(img)
    run[f'Plots/{title}'].upload(fig)


def on_pretrain_routine_start(trainer):
    """Callback function called before the training routine starts."""
    try:
        global run
        run = neptune.init_run(project=trainer.args.project or 'YOLOv8', name=trainer.args.name, tags=['YOLOv8'])
        run['Configuration/Hyperparameters'] = {k: '' if v is None else v for k, v in vars(trainer.args).items()}
    except Exception as e:
        LOGGER.warning(f'WARNING ⚠️ NeptuneAI installed but not initialized correctly, not logging this run. {e}')


def on_train_epoch_end(trainer):
    """Callback function called at end of each training epoch."""
    _log_scalars(trainer.label_loss_items(trainer.tloss, prefix='train'), trainer.epoch + 1)
    _log_scalars(trainer.lr, trainer.epoch + 1)
    if trainer.epoch == 1:
        _log_images({f.stem: str(f) for f in trainer.save_dir.glob('train_batch*.jpg')}, 'Mosaic')


def on_fit_epoch_end(trainer):
    """Callback function called at end of each fit (train+val) epoch."""
    if run and trainer.epoch == 0:
        model_info = {
            'parameters': get_num_params(trainer.model),
            'GFLOPs': round(get_flops(trainer.model), 3),
            'speed(ms)': round(trainer.validator.speed['inference'], 3)}
        run['Configuration/Model'] = model_info
    _log_scalars(trainer.metrics, trainer.epoch + 1)


def on_val_end(validator):
    """Callback function called at end of each validation."""
    if run:
        # Log val_labels and val_pred
        _log_images({f.stem: str(f) for f in validator.save_dir.glob('val*.jpg')}, 'Validation')


def on_train_end(trainer):
    """Callback function called at end of training."""
    if run:
        # Log final results, CM matrix + PR plots
        files = ['results.png', 'confusion_matrix.png', *(f'{x}_curve.png' for x in ('F1', 'PR', 'P', 'R'))]
        files = [(trainer.save_dir / f) for f in files if (trainer.save_dir / f).exists()]  # filter
        for f in files:
            _log_plot(title=f.stem, plot_path=f)
        # Log the final model
        run[f'weights/{trainer.args.name or trainer.args.task}/{str(trainer.best.name)}'].upload(File(str(
            trainer.best)))
        run.stop()


callbacks = {
    'on_pretrain_routine_start': on_pretrain_routine_start,
    'on_train_epoch_end': on_train_epoch_end,
    'on_fit_epoch_end': on_fit_epoch_end,
    'on_val_end': on_val_end,
    'on_train_end': on_train_end} if neptune else {}
