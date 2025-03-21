import inspect
import os
import logging
from functools import wraps

def setup_logging():
    # Check if the root logger is already configured
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        # If the root logger is already configured, use its setup
        return

    log_file_path = os.environ.get('PYTHON_LOG_PATH')

    # Only configure logging if log file path is set (and the root logger is not configured)
    if log_file_path:
        root_logger = logging.getLogger()
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        # Set log level from environment variable or default to INFO
        log_level = logging.INFO
        log_level_config = os.environ.get('PYTHON_LOG_LEVEL')

        if log_level_config == 'DEBUG':
            log_level = logging.DEBUG
        elif log_level_config == 'WARNING':
            log_level = logging.WARNING
        elif log_level_config == 'ERROR':
            log_level = logging.ERROR
        elif log_level_config == 'CRITICAL':
            log_level = logging.CRITICAL

        # Configure file handler only, no stdout logging
        file_handler = logging.FileHandler(log_file_path)
        formatter = logging.Formatter(format_str)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(log_level)

# Export the logger, named for this module
setup_logging()

logger = logging.getLogger(__name__)

def log_function_call(func, logger = logger):
    @wraps(func)
    def wrapper(*args, **kwargs):
        signature = inspect.signature(func)
        bound_args = signature.bind(*args, **kwargs)
        bound_args.apply_defaults()
        # Log function name and arguments
        logger.debug("Calling %s with args: %s", func.__name__, bound_args.arguments)

        try:
            # Call the original function
            result = func(*args, **kwargs)

            # Log the return value
            logger.debug("%s returned %s", func.__name__, result)
            return result

        except Exception as e:
            # Log the exception with traceback
            logger.exception("Exception occurred in %s: %s", func.__name__, e)
            raise  # Re-raise the exception after logging it

    return wrapper

# For logging all methods in some class vvvvvv
def log_instance_method_calls(instance: object, enabled: bool):
    if not enabled:
        return instance

    classLogger = logging.getLogger(f"{instance.__module__}:{instance.__class__.__name__}")
    for attr_name in dir(instance):
        if not attr_name.startswith('_'):  # Avoid private and protected methods
            attr = getattr(instance, attr_name)
            if callable(attr) and not hasattr(attr, "_wrapped"):  # Avoid double wrapping
                wrapped = log_function_call(attr, classLogger)
                wrapped._wrapped = True
                setattr(instance, attr_name, wrapped)

    return instance
